"""MMT inspect command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_mmt, resolve_teamspace


@click.command("inspect", cls=LightningCommand)
@click.option("--name", default=None, help="The multi-machine job name. Required.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def inspect_mmt(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Inspect a multi-machine job for further details as JSON."""
    resolved_teamspace = resolve_teamspace(teamspace)
    mmt = resolve_mmt(name, resolved_teamspace)
    Console().print(mmt.json())
