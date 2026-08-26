"""Job list command."""

from contextlib import suppress
from datetime import datetime
from typing import Optional

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.job import Job
from lightning_sdk.models import _list_teamspaces


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
    type=click.Choice(
        ["name", "teamspace", "status", "studio", "machine", "image", "cloud-account", "started", "stopped"],
        case_sensitive=False,
    ),
    help="the attribute to sort the jobs by.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_jobs(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[str] = None,
    as_json: bool = False,
) -> None:
    """List jobs for a given teamspace.

    Includes both single- and multi-machine jobs.
    """
    resources: list[Job] = []
    if all and not teamspace:
        for teamspace_slug in _list_teamspaces():
            resolved = resolve_teamspace(teamspace_slug)
            resources.extend(resolved.jobs)
    else:
        resolved = resolve_teamspace(teamspace)
        resources.extend(resolved.jobs)

    rows = []
    for job in resources:
        job._prevent_refetch_latest = True
        with suppress(RuntimeError):
            rows.append(
                {
                    "name": job.name,
                    "teamspace": f"{job.teamspace.owner.name}/{job.teamspace.name}",
                    "studio": job.studio_name,
                    "image": job.image,
                    "status": str(job.status) if job.status is not None else None,
                    "started_at": getattr(job, "started_at", None),
                    "stopped_at": getattr(job, "stopped_at", None),
                    "machine": str(job.machine),
                    "num_machines": getattr(job, "num_machines", 1),
                    "total_cost": round(job.total_cost, 3),
                    "_cloud_account": str(getattr(job, "cloud_account", "") or ""),
                }
            )

    sort_by = sort_by or "name"
    sort_key = {"cloud-account": "_cloud_account", "started": "started_at", "stopped": "stopped_at"}.get(
        sort_by, sort_by
    )
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
        "Studio",
        "Image",
        "Status",
        "Started",
        "Stopped",
        "Machine",
        "Num Machines",
        "Total Cost",
    ):
        table.add_column(column)
    for row in rows:
        table.add_row(
            str(row["name"] or ""),
            str(row["teamspace"] or ""),
            str(row["studio"] or ""),
            str(row["image"] or ""),
            str(row["status"] or ""),
            _format_timestamp(row["started_at"]),
            _format_timestamp(row["stopped_at"]),
            str(row["machine"] or ""),
            str(row["num_machines"]),
            f"{row['total_cost']:.3f}",
        )
    Console().print(table)


def _format_timestamp(value: object) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime) else ""
