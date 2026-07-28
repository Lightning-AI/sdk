"""Job delete command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_teamspace


@click.command("delete", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the job from. "
        "Should be specified as {owner}/{name} "
        "If not provided, uses the configured default teamspace."
    ),
)
def delete_job(name: str, teamspace: Optional[str] = None) -> None:
    """Delete a job."""
    resolved_teamspace = resolve_teamspace(teamspace)
    job = resolve_job(name, resolved_teamspace)
    job.delete()
    Console().print(f"Successfully deleted {job.name}!")
