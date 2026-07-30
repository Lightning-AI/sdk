"""Job list command."""

from contextlib import suppress
from typing import Optional

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
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
        ["name", "teamspace", "status", "studio", "machine", "image", "cloud-account"], case_sensitive=False
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
    resources = []
    if all and not teamspace:
        for teamspace_slug in _list_teamspaces():
            resolved = resolve_teamspace(teamspace_slug)
            resources.extend(resolved.jobs)
            resources.extend(resolved.multi_machine_jobs)
    else:
        resolved = resolve_teamspace(teamspace)
        resources.extend(resolved.jobs)
        resources.extend(resolved.multi_machine_jobs)

    rows = []
    for job in resources:
        job._prevent_refetch_latest = True
        with suppress(RuntimeError):
            studio = job.studio
            rows.append(
                {
                    "name": job.name,
                    "teamspace": f"{job.teamspace.owner.name}/{job.teamspace.name}",
                    "studio": studio.name if studio else None,
                    "image": job.image,
                    "status": str(job.status) if job.status is not None else None,
                    "machine": str(job.machine),
                    "num_machines": getattr(job, "num_machines", 1),
                    "total_cost": round(job.total_cost, 3),
                    "_cloud_account": str(job.cloud_account),
                }
            )

    sort_key = "_cloud_account" if sort_by == "cloud-account" else sort_by or "name"
    rows.sort(key=lambda row: str(row.get(sort_key) or ""))
    if as_json:
        echo_json([{key: value for key, value in row.items() if not key.startswith("_")} for row in rows])
        return

    table = Table(pad_edge=True)
    for column in ("Name", "Teamspace", "Studio", "Image", "Status", "Machine", "Num Machines", "Total Cost"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["name"],
            row["teamspace"],
            row["studio"],
            row["image"],
            row["status"],
            row["machine"],
            str(row["num_machines"]),
            f"{row['total_cost']:.3f}",
        )
    Console().print(table)
