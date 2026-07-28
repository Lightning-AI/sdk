"""Shared pieces for the per-resource log commands.

Logs are read one resource at a time — ``lightning job logs``, ``lightning mmt logs``,
``lightning deployment logs``, ``lightning sandbox logs`` — and this module holds what more than
one of them needs: time-bound parsing, query highlighting, and the read-and-print loop for a
command that merges several resources into one stream.

The client itself is :class:`~lightning_sdk.api.logs_api.LogsApi`, and single-resource commands
go through their SDK object (``Job.logs``, ``MMT.logs``) rather than this reader.
"""

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Sequence

import rich_click as click

from lightning_sdk.api.logs_api import LogsApi
from lightning_sdk.cli.utils.json_output import echo_json

# Lightning brand purple (#a78bfa) as an RGB tuple for truecolor styling.
_MATCH_COLOR = (167, 139, 250)

# A resource whose logs are not in the current storage format has no saved lines to print.
# Rather than show nothing, briefly tail the live stream and stop once it goes quiet.
LIVE_FALLBACK_IDLE_TIMEOUT = 8

_RELATIVE_TIME = re.compile(r"^(\d+)([smhdw])$")
_RELATIVE_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def highlight(text: str, query: Optional[str]) -> str:
    """Wrap case-insensitive occurrences of ``query`` in ``text`` with a match style.

    click.echo strips these ANSI codes automatically when stdout is not a terminal, so
    piped/redirected output stays plain.
    """
    if not query:
        return text
    return re.sub(
        re.escape(query),
        lambda m: click.style(m.group(0), fg=_MATCH_COLOR, bold=True),
        text,
        flags=re.IGNORECASE,
    )


def resolve_time(value: Optional[str], flag: str) -> Optional[str]:
    """Turn a relative bound like ``2h`` into the RFC3339 timestamp the API expects.

    An RFC3339 value is passed through. Anything else is rejected here: the server ignores a
    bound it cannot parse, which would silently widen the read instead of failing.
    """
    if not value:
        return None
    match = _RELATIVE_TIME.match(value.strip())
    if match:
        amount, unit = match.groups()
        delta = timedelta(**{_RELATIVE_UNITS[unit]: int(amount)})
        return (datetime.now(timezone.utc) - delta).isoformat()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise click.UsageError(
            f"{flag} must be a duration like 30s/5m/2h/3d/1w, or an RFC3339 timestamp. Got {value!r}."
        ) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


@dataclass
class LogSelection:
    """A resolved set of log sources, plus display names for the resources behind them."""

    teamspace_id: str
    job_ids: Sequence[str] = ()
    deployment_id: Optional[str] = None
    mmt_id: Optional[str] = None
    sandbox_id: Optional[str] = None
    sandbox_command_ids: Sequence[str] = ()
    # resource id -> label, used to mark which replica or machine a line came from. Empty when
    # only one resource can appear, so single-resource output stays unprefixed.
    labels: Dict[str, str] = field(default_factory=dict)

    def selectors(self) -> Dict[str, object]:
        return {
            "job_ids": list(self.job_ids),
            "deployment_id": self.deployment_id,
            "mmt_id": self.mmt_id,
            "sandbox_id": self.sandbox_id,
            "sandbox_command_ids": list(self.sandbox_command_ids),
        }


def read_logs(
    selection: LogSelection,
    *,
    query: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    tail: Optional[int] = None,
    follow: bool = False,
    timestamps: bool = False,
    tail_anchor: Optional[object] = None,
    api_key: Optional[str] = None,
    as_json: bool = False,
) -> None:
    """Read and print logs for ``selection``, labelling lines by the resource they came from.

    The history is paginated automatically, then the live stream is tailed when following.
    ``tail`` searches back in widening windows instead of reading a long history in full.
    With ``as_json`` the entries are collected and printed as a single JSON array instead of
    formatted lines; it cannot be combined with ``follow`` (an unbounded stream has no end).
    """
    if as_json and follow:
        raise click.ClickException("--json cannot be combined with --follow.")

    printed = 0
    rows = []
    try:
        entries = LogsApi(api_key=api_key).stream(
            selection.teamspace_id,
            since=since,
            until=until,
            query=query,
            severity=severity,
            follow=follow,
            tail=tail,
            tail_anchor=tail_anchor,
            idle_timeout=None if follow else LIVE_FALLBACK_IDLE_TIMEOUT,
            # Nothing saved yet for a running resource: tail its live stream so a snapshot still
            # shows something.
            fallback_to_live=not follow,
            **selection.selectors(),
        )
        for entry in entries:
            label = selection.labels.get(entry.resource_id) if selection.labels else None
            if as_json:
                rows.append(entry.to_json_dict(label))
                printed += 1
                continue
            # Highlighting the message before formatting keeps the timestamp and label out of it.
            line = replace(entry, message=highlight(entry.message, query)).format(timestamps=timestamps, prefix=label)
            click.echo(line)
            printed += 1
    except KeyboardInterrupt:
        pass
    except RuntimeError as ex:
        raise click.ClickException(str(ex)) from ex

    if as_json:
        echo_json(rows)
        return

    if not printed:
        click.echo("No logs matched.", err=True)


def deployment_replica_labels(teamspace_id: str, deployment_id: str) -> Dict[str, str]:
    """Map a deployment's replica job ids to their names, for labelling merged output."""
    from lightning_sdk.api.deployment_api import DeploymentApi

    jobs = DeploymentApi().list_deployment_jobs(teamspace_id, deployment_id, limit=100)
    return {job.id: job.name or job.id for job in jobs} if len(jobs) > 1 else {}
