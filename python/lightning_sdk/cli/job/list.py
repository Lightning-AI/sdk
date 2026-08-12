"""Job list command."""

from contextlib import suppress
from typing import Optional

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.job import Job
from lightning_sdk.machine import Machine
from lightning_sdk.models import _list_teamspaces
from lightning_sdk.utils.resolve import _get_org_id

# Shared across the list command so accelerator lookups hit CloudAccountApi's
# per-instance lru_cache instead of creating a fresh client for every job.
_cloud_account_api = CloudAccountApi()


def _machine_label(job: Job) -> str:
    """Resolve a job's machine display name without per-job API client churn.

    ``Job.machine`` creates a new ``CloudAccountApi`` on every access, so listing
    N jobs pays ~3 HTTP calls each. Reuse one client and match against the
    already-fetched job spec, falling back to ``Machine.from_str`` like the
    accelerator path does when no record matches.
    """
    spec = job._guaranteed_job.spec
    accelerators = _cloud_account_api.list_cloud_account_accelerators(
        teamspace_id=job.teamspace.id,
        cloud_account_id=spec.cluster_id,
        org_id=_get_org_id(job.teamspace),
    )
    enabled = [a for a in (accelerators.accelerator or []) if a.enabled] if accelerators else []
    for accelerator in enabled:
        identifiers = (accelerator.slug, accelerator.slug_multi_cloud, accelerator.instance_id)
        if (spec.instance_name and spec.instance_name in identifiers) or (
            spec.instance_type and spec.instance_type in identifiers
        ):
            return str(Machine._from_accelerator(accelerator))
    return str(Machine.from_str(spec.instance_name or spec.instance_type or ""))


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
            spec = job._guaranteed_job.spec
            rows.append(
                {
                    "name": job.name,
                    "teamspace": f"{job.teamspace.owner.name}/{job.teamspace.name}",
                    "studio": job.studio_name,
                    "image": job.image,
                    "status": str(job.status) if job.status is not None else None,
                    "machine": _machine_label(job),
                    "num_machines": getattr(job, "num_machines", 1),
                    "total_cost": round(job.total_cost, 3),
                    "_cloud_account": spec.cluster_id or "",
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
            str(row["name"] or ""),
            str(row["teamspace"] or ""),
            str(row["studio"] or ""),
            str(row["image"] or ""),
            str(row["status"] or ""),
            str(row["machine"] or ""),
            str(row["num_machines"]),
            f"{row['total_cost']:.3f}",
        )
    Console().print(table)
