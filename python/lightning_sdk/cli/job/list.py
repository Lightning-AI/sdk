"""Job list command."""

from contextlib import suppress
from datetime import datetime
from fnmatch import fnmatchcase
from typing import Dict, List, Optional, Sequence, Tuple, cast

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.cli.job.run import _resolve_tags
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.job import Job
from lightning_sdk.models import _list_teamspaces

# The keys `--sort-by` and `--filter` both accept. Keep the two in parity: a key that can be sorted
# on can also be filtered on, so anything added here must resolve through `_ROW_KEYS` below.
LIST_KEYS = (
    "name",
    "teamspace",
    "creator",
    "status",
    "studio",
    "machine",
    "image",
    "cloud-account",
    "started",
    "stopped",
)

# Keys whose row field is named differently from the key itself.
_ROW_KEYS = {"cloud-account": "_cloud_account", "started": "started_at", "stopped": "stopped_at"}


@click.command("list", cls=LightningCommand)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list jobs from. Should be specified as {owner}/{name}. Defaults to the configured teamspace."
    ),
)
@click.option(
    "--all",
    is_flag=True,
    flag_value=True,
    default=False,
    help="if teamspace is not provided, list all jobs in all teamspaces.",
)
@click.option(
    "--sort-by",
    "--sort_by",
    default=None,
    type=click.Choice(list(LIST_KEYS), case_sensitive=False),
    help="the attribute to sort the jobs by.",
)
@click.option(
    "--filter",
    "filters",
    default=(),
    multiple=True,
    metavar="KEY=PATTERN",
    help=(
        "Only list jobs whose KEY matches PATTERN, a case-insensitive glob. Can be a comma-separated list "
        "or passed multiple times, and every filter has to match. "
        f"KEY is one of: {', '.join(LIST_KEYS)}."
    ),
)
@click.option(
    "--tags",
    "--tag",
    "tags",
    default=(),
    multiple=True,
    help=(
        "Only list jobs carrying at least one of these tags. Can be a comma-separated list or passed multiple times."
    ),
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_jobs(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[str] = None,
    filters: Sequence[str] = (),
    tags: Sequence[str] = (),
    as_json: bool = False,
) -> None:
    """List jobs for a given teamspace.

    Includes both single- and multi-machine jobs.

    Example:
        lightning job list --filter 'name=train-*'
        lightning job list --filter 'creator=justus,status=running'
        lightning job list --all --sort-by started

    """
    wanted_tags = _resolve_tags(tags)
    wanted_filters = _resolve_filters(filters)

    resources: list[Job] = []
    if all and not teamspace:
        for teamspace_slug in _list_teamspaces():
            resolved = resolve_teamspace(teamspace_slug)
            resources.extend(resolved.list_jobs(tags=wanted_tags))
    else:
        resolved = resolve_teamspace(teamspace)
        resources.extend(resolved.list_jobs(tags=wanted_tags))

    usernames: Dict[str, Dict[str, str]] = {}

    rows = []
    for job in resources:
        job._prevent_refetch_latest = True
        with suppress(RuntimeError):
            rows.append(
                {
                    "name": job.name,
                    "teamspace": f"{job.teamspace.owner.name}/{job.teamspace.name}",
                    "creator": _creator(job, usernames),
                    "studio": job.studio_name,
                    "image": job.image,
                    "status": str(job.status) if job.status is not None else None,
                    "started_at": getattr(job, "started_at", None),
                    "stopped_at": getattr(job, "stopped_at", None),
                    "machine": str(job.machine),
                    "num_machines": getattr(job, "num_machines", 1),
                    "total_cost": round(job.total_cost, 3),
                    "tags": list(job.tags),
                    "_cloud_account": str(getattr(job, "cloud_account", "") or ""),
                }
            )

    rows = [row for row in rows if _matches_filters(row, wanted_filters)]

    sort_by = sort_by or "name"
    sort_key = _ROW_KEYS.get(sort_by, sort_by)
    rows.sort(key=lambda row: str(row.get(sort_key) or ""))
    if as_json:
        echo_json(
            [
                {
                    key: value.isoformat() if isinstance(value, datetime) else value
                    for key, value in row.items()
                    if not key.startswith("_")
                }
                for row in rows
            ]
        )
        return

    table = Table(pad_edge=True)
    for column in (
        "Name",
        "Teamspace",
        "Creator",
        "Studio",
        "Image",
        "Status",
        "Started",
        "Stopped",
        "Machine",
        "Num Machines",
        "Total Cost",
        "Tags",
    ):
        table.add_column(column)
    for row in rows:
        table.add_row(
            str(row["name"] or ""),
            str(row["teamspace"] or ""),
            str(row["creator"] or ""),
            str(row["studio"] or ""),
            str(row["image"] or ""),
            str(row["status"] or ""),
            _format_timestamp(row["started_at"]),
            _format_timestamp(row["stopped_at"]),
            str(row["machine"] or ""),
            str(row["num_machines"]),
            f"{row['total_cost']:.3f}",
            ", ".join(cast(List[str], row["tags"])),
        )
    Console().print(table)


def _resolve_filters(filters: Sequence[str]) -> Tuple[Tuple[str, str], ...]:
    """Flatten comma-separated and repeated --filter values into KEY=PATTERN pairs.

    Keys that `--sort-by` does not accept are rejected here, which keeps the two options in parity.
    """
    resolved = []
    for value in filters:
        for entry in value.split(","):
            raw = entry.strip()
            if not raw:
                continue

            key, separator, pattern = raw.partition("=")
            key, pattern = key.strip().lower(), pattern.strip()
            if not separator or not key:
                raise click.BadParameter(f"expected KEY=PATTERN, got {raw!r}", param_hint="'--filter'")
            if key not in LIST_KEYS:
                raise click.BadParameter(
                    f"unknown key {key!r}. Filter by one of: {', '.join(LIST_KEYS)}", param_hint="'--filter'"
                )
            resolved.append((key, pattern))

    return tuple(resolved)


def _matches_filters(row: Dict[str, object], filters: Sequence[Tuple[str, str]]) -> bool:
    """Whether a row matches every filter, comparing patterns against the values as displayed."""
    for key, pattern in filters:
        value = row.get(_ROW_KEYS.get(key, key))
        text = _format_timestamp(value) if isinstance(value, datetime) else str(value or "")
        if not fnmatchcase(text.lower(), pattern.lower()):
            return False
    return True


def _creator(job: Job, usernames: Dict[str, Dict[str, str]]) -> str:
    """Return the username of whoever created ``job``, falling back to their raw user id.

    ``usernames`` caches one lookup per teamspace across the whole listing.
    """
    user_id = getattr(getattr(job, "_job", None), "user_id", None)
    teamspace_id = getattr(job.teamspace, "id", None)
    if not user_id or not teamspace_id:
        return ""

    if teamspace_id not in usernames:
        # A teamspace whose members we cannot read still lists its jobs, so fall back to the raw id.
        usernames[teamspace_id] = {}
        with suppress(Exception):
            usernames[teamspace_id] = TeamspaceApi().list_member_usernames(teamspace_id=teamspace_id)

    return usernames[teamspace_id].get(user_id, user_id)


def _format_timestamp(value: object) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime) else ""
