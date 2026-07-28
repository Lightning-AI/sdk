"""Job inspect command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("inspect", cls=LightningCommand)
@click.argument("name", required=False, help="The job name. Required.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified, uses the configured default teamspace."
    ),
)
def inspect_job(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Inspect a job for further details as JSON."""
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)
    Console().print(job.json())
