"""MMT delete command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_mmt, resolve_teamspace


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
def delete_mmt(name: str, teamspace: Optional[str] = None) -> None:
    """Delete a multi-machine job."""
    resolved_teamspace = resolve_teamspace(teamspace)
    mmt = resolve_mmt(name, resolved_teamspace)
    mmt.delete()
    Console().print(f"Successfully deleted {mmt.name}!")
