"""Top-level `lightning logs` command.

The single place logs are read and rendered for the CLI. `lightning job logs` and
`lightning deployment logs` are shortcuts that resolve their resource and hand off to
:func:`read_logs` here, so all three print the same way and cannot drift apart.
"""

import json
import re
import shlex
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import rich_click as click

from lightning_sdk.api.logs_api import SEVERITIES, LogEntry, LogsApi
from lightning_sdk.cli.utils.logging import LightningCommand

_SEVERITIES = list(SEVERITIES)

# Lightning brand purple (#a78bfa) as an RGB tuple for truecolor styling.
_MATCH_COLOR = (167, 139, 250)

# A resource whose logs are not in the current storage format has no saved lines to print.
# Rather than show nothing, briefly tail the live stream and stop once it goes quiet.
LIVE_FALLBACK_IDLE_TIMEOUT = 8

_RELATIVE_SINCE = re.compile(r"^(\d+)([smhdw])$")
_RELATIVE_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def _highlight(text: str, query: Optional[str]) -> str:
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
    match = _RELATIVE_SINCE.match(value.strip())
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


def _exclusive(id_value: Optional[str], name_value: Optional[str], resource: str) -> None:
    if id_value and name_value:
        raise click.UsageError(f"Pass only one of --{resource}-id / --{resource}-name.")


def _next_page_command(base_flags: List[Tuple[str, str]], timestamps: bool, next_token: str) -> str:
    """Render a copy-paste command that fetches the next page with the same filters."""
    parts = ["lightning", "logs"]
    for flag, value in base_flags:
        parts += [flag, shlex.quote(str(value))]
    if not timestamps:
        parts.append("--no-timestamps")
    parts += ["--page-token", shlex.quote(next_token)]
    return " ".join(parts)


def _resolve_sandbox_id(name: str, teamspace: "object") -> str:
    from lightning_sdk.sandbox.sandbox import Sandbox

    client = Sandbox()
    page_token: Optional[str] = None
    try:
        while True:
            result = client.list(teamspace=teamspace, page_token=page_token)
            for sandbox in result.sandboxes:
                if sandbox.name == name:
                    return sandbox.sandbox_id
            page_token = result.next_page_token or None
            if not page_token:
                break
    except RuntimeError as ex:
        # Listing sandboxes hits the sandbox API, which the server gates behind a
        # teamspace/org-scoped key — a personal login key gets a 403. The logs endpoint
        # itself takes --sandbox-id directly with the normal login, so point there.
        raise click.ClickException(
            "Looking up a sandbox by name requires a teamspace- or org-scoped API key "
            "(set LIGHTNING_SANDBOX_API_KEY); a personal login key can't list sandboxes. "
            "Pass --sandbox-id instead — it works with your normal login."
        ) from ex
    raise click.ClickException(f"No sandbox named '{name}' found in {teamspace.name}. Pass --sandbox-id instead.")


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


def _entry_json(entry: LogEntry) -> Dict[str, object]:
    return {
        "timestamp": entry.timestamp.isoformat() if entry.timestamp is not None else None,
        "message": entry.message,
        "severity": entry.severity,
        "resource_id": entry.resource_id,
        "line": entry.line,
    }


def read_logs(
    selection: LogSelection,
    *,
    query: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    tail: Optional[int] = None,
    limit: Optional[int] = None,
    page_token: Optional[str] = None,
    follow: bool = False,
    timestamps: bool = False,
    as_json: bool = False,
    tail_anchor: Optional[object] = None,
    next_page_flags: Optional[List[Tuple[str, str]]] = None,
) -> None:
    """Read and print logs for ``selection``.

    Two modes, chosen by the flags:

    - ``tail`` or ``follow``: stream. The history is paginated automatically, then the live
      stream is tailed when following. ``tail`` searches back in widening windows instead of
      reading a long history in full.
    - otherwise: fetch a single page and print the cursor for the next one, which is what makes
      ``--limit``/``--page-token`` a predictable way to walk a large range.
    """
    api = LogsApi()
    selectors = selection.selectors()

    def render(entry: LogEntry) -> str:
        label = selection.labels.get(entry.resource_id) if selection.labels else None
        # Highlighting the message before formatting keeps the timestamp and label out of it.
        return replace(entry, message=_highlight(entry.message, query)).format(timestamps=timestamps, prefix=label)

    if tail is not None or follow:
        entries = api.stream(
            selection.teamspace_id,
            since=since,
            until=until,
            query=query,
            severity=severity,
            follow=follow,
            tail=tail,
            tail_anchor=tail_anchor,
            idle_timeout=None if follow else LIVE_FALLBACK_IDLE_TIMEOUT,
            # Nothing saved yet for a running resource: tail its live stream so a snapshot
            # still shows something.
            fallback_to_live=not follow,
            **selectors,
        )
        printed = 0
        try:
            for entry in entries:
                click.echo(json.dumps(_entry_json(entry)) if as_json else render(entry))
                printed += 1
        except KeyboardInterrupt:
            pass
        except RuntimeError as ex:
            raise click.ClickException(str(ex)) from ex
        if not printed and not as_json:
            click.echo("No logs matched.", err=True)
        return

    page = api.get_page(
        selection.teamspace_id,
        since=since,
        until=until,
        query=query,
        severity=severity,
        page_size=limit,
        page_token=page_token,
        **selectors,
    )

    if as_json:
        click.echo(
            json.dumps(
                {
                    "entries": [_entry_json(entry) for entry in page.entries],
                    "next_page_token": page.next_page_token,
                    "follow_url": page.follow_url,
                },
                indent=2,
            )
        )
        return

    for entry in page.entries:
        click.echo(render(entry))

    # Cursor hint goes to stderr so piping stdout (e.g. `| grep`) stays clean.
    if page.next_page_token and next_page_flags is not None:
        click.echo("\nNext page — run:", err=True)
        click.echo(f"  {_next_page_command(next_page_flags, timestamps, page.next_page_token)}", err=True)
    elif not page.entries:
        click.echo("No logs matched.", err=True)


def deployment_replica_labels(teamspace_id: str, deployment_id: str) -> Dict[str, str]:
    """Map a deployment's replica job ids to their names, for labelling merged output."""
    from lightning_sdk.api.deployment_api import DeploymentApi

    jobs = DeploymentApi().list_deployment_jobs(teamspace_id, deployment_id, limit=100)
    return {job.id: job.name or job.id for job in jobs} if len(jobs) > 1 else {}


@click.command("logs", cls=LightningCommand)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to search logs in, as {owner}/{name} (e.g. my-org/my-teamspace). "
        "If not provided, can be selected interactively."
    ),
)
@click.option("--job-id", "--job_id", "job_ids", multiple=True, help="restrict to a job (by id). Can be repeated.")
@click.option("--job-name", "--job_name", "job_name", default=None, help="restrict to a job (by name).")
@click.option(
    "--deployment-id", "--deployment_id", "deployment_id", default=None, help="restrict to a deployment (by id)."
)
@click.option(
    "--deployment-name",
    "--deployment_name",
    "deployment_name",
    default=None,
    help="restrict to a deployment (by name).",
)
@click.option("--mmt-id", "--mmt_id", "mmt_id", default=None, help="restrict to a multi-machine job (by id).")
@click.option("--mmt-name", "--mmt_name", "mmt_name", default=None, help="restrict to a multi-machine job (by name).")
@click.option("--sandbox-id", "--sandbox_id", "sandbox_id", default=None, help="restrict to a sandbox (by id).")
@click.option("--sandbox-name", "--sandbox_name", "sandbox_name", default=None, help="restrict to a sandbox (by name).")
@click.option(
    "--sandbox-command-id",
    "--sandbox_command_id",
    "sandbox_command_id",
    default=None,
    help="restrict to a single sandbox command (by id).",
)
@click.option("--query", "-q", default=None, help="only return lines matching this text.")
@click.option(
    "--severity",
    default=None,
    type=click.Choice(_SEVERITIES, case_sensitive=False),
    help="minimum severity to include (error > warning > info > debug).",
)
@click.option("--since", default=None, help='only lines at or after this time (e.g. "2h", RFC3339).')
@click.option("--until", default=None, help='only lines at or before this time (e.g. "30m", RFC3339).')
@click.option("--tail", "-t", "tail", default=None, type=int, help="only show the last N lines.")
@click.option("--follow", "-f", is_flag=True, default=False, help="stream new lines as they are produced.")
@click.option(
    "--limit", "-n", "limit", default=None, type=int, help="maximum number of lines per page, read oldest first."
)
@click.option(
    "--page-token",
    "--page_token",
    "page_token",
    default=None,
    help="cursor from a previous run's next page token, to fetch the following page.",
)
@click.option("--timestamps/--no-timestamps", default=True, help="prefix each line with its timestamp.")
@click.option("--json", "as_json", is_flag=True, help="emit entries and the next page token as JSON.")
def logs(
    teamspace: Optional[str],
    job_ids: Sequence[str],
    job_name: Optional[str],
    deployment_id: Optional[str],
    deployment_name: Optional[str],
    mmt_id: Optional[str],
    mmt_name: Optional[str],
    sandbox_id: Optional[str],
    sandbox_name: Optional[str],
    sandbox_command_id: Optional[str],
    query: Optional[str],
    severity: Optional[str],
    since: Optional[str],
    until: Optional[str],
    tail: Optional[int],
    follow: bool,
    limit: Optional[int],
    page_token: Optional[str],
    timestamps: bool,
    as_json: bool,
) -> None:
    """Search and page through a teamspace's logs.

    To read one resource's logs, prefer the per-resource commands — same output, less typing:

      lightning job logs my-job --tail 100
      lightning deployment logs my-api --follow --severity warning
      lightning mmt logs my-mmt --query error
      lightning sandbox logs sbx-42

    Use this command to select by id, or to walk a large range with an explicit cursor. Filter by
    resource (--job-id/--job-name, --deployment-id/--deployment-name, --mmt-id/--mmt-name,
    --sandbox-id/--sandbox-name, --sandbox-command-id), text (--query), severity and time range.
    --tail shows the last N lines and --follow streams new ones; without either, results are
    paginated oldest-first and the cursor for the next page is printed at the end.

    Examples:
      lightning logs --job-id job-123 --tail 100
      lightning logs --deployment-name my-api --query error --since 2h
      lightning logs --sandbox-id sbx-42 --sandbox-command-id cmd-abc
      lightning logs --job-id job-123 --page-token <token>
    """
    from lightning_sdk.api.deployment_api import DeploymentApi
    from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction

    _exclusive(job_ids[0] if job_ids else None, job_name, "job")
    _exclusive(deployment_id, deployment_name, "deployment")
    _exclusive(mmt_id, mmt_name, "mmt")
    _exclusive(sandbox_id, sandbox_name, "sandbox")
    if tail is not None and limit is not None:
        raise click.UsageError("Pass only one of --tail (last N lines) / --limit (page size, oldest first).")
    if follow and page_token:
        raise click.UsageError("--page-token reads a fixed page, so it cannot be combined with --follow.")

    # Captured before resolution rewrites the *_id vars, so the reproduced next-page
    # command reflects the filters the user actually typed. --page-token is added fresh.
    next_page_flags: List[Tuple[str, str]] = [
        (flag, value)
        for flag, value in (
            ("--teamspace", teamspace),
            *(("--job-id", job) for job in job_ids),
            ("--job-name", job_name),
            ("--deployment-id", deployment_id),
            ("--deployment-name", deployment_name),
            ("--mmt-id", mmt_id),
            ("--mmt-name", mmt_name),
            ("--sandbox-id", sandbox_id),
            ("--sandbox-name", sandbox_name),
            ("--sandbox-command-id", sandbox_command_id),
            ("--query", query),
            ("--severity", severity),
            ("--since", since),
            ("--until", until),
            ("--limit", str(limit) if limit is not None else None),
        )
        if value
    ]

    action = _JobAndMMTAction()
    resolved_teamspace = action(teamspace)

    resolved_job_ids = list(job_ids)
    if job_name is not None:
        resolved_job_ids = [action._resolve_job(job_name, teamspace=resolved_teamspace).resource_id]

    if mmt_name is not None:
        mmt_id = action._resolve_mmt(mmt_name, teamspace=resolved_teamspace).resource_id

    if deployment_name is not None:
        deployment = DeploymentApi().get_deployment_by_name(deployment_name, resolved_teamspace.id)
        if deployment is None:
            raise click.ClickException(f"No deployment named '{deployment_name}' found in {resolved_teamspace.name}.")
        deployment_id = deployment.id

    if sandbox_name is not None:
        sandbox_id = _resolve_sandbox_id(sandbox_name, resolved_teamspace)

    if not (resolved_job_ids or deployment_id or mmt_id or sandbox_id or sandbox_command_id):
        raise click.UsageError(
            "Pick what to read logs for: --job-name/--job-id, --deployment-name/--deployment-id, "
            "--mmt-name/--mmt-id or --sandbox-name/--sandbox-id."
        )

    labels: Dict[str, str] = {}
    if deployment_id:
        labels = deployment_replica_labels(resolved_teamspace.id, deployment_id)
    elif mmt_id:
        labels = _mmt_machine_labels(mmt_id, resolved_teamspace, action)

    read_logs(
        LogSelection(
            teamspace_id=resolved_teamspace.id,
            job_ids=resolved_job_ids,
            deployment_id=deployment_id,
            mmt_id=mmt_id,
            sandbox_id=sandbox_id,
            sandbox_command_ids=[sandbox_command_id] if sandbox_command_id else (),
            labels=labels,
        ),
        query=query,
        severity=severity.lower() if severity else None,
        since=resolve_time(since, "--since"),
        until=resolve_time(until, "--until"),
        tail=tail,
        limit=limit,
        page_token=page_token,
        follow=follow,
        timestamps=timestamps,
        as_json=as_json,
        next_page_flags=next_page_flags,
    )


def _mmt_machine_labels(mmt_id: str, teamspace: "object", action: "object") -> Dict[str, str]:
    """Map a multi-machine job's per-rank job ids to their machine names."""
    from lightning_sdk.api.mmt_api import MMTApiV2

    subjobs = MMTApiV2().list_mmt_subjobs(mmt_id, teamspace.id)
    return {job.id: job.name or job.id for job in subjobs} if len(subjobs) > 1 else {}
