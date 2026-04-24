"""MMT delete command."""

from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction


@click.command("delete")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the job from. "
        "Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
def delete_mmt(name: str, teamspace: Optional[str] = None) -> None:
    """Delete a multi-machine job."""
    menu = _JobAndMMTAction()
    mmt = menu.mmt(name=name, teamspace=teamspace)
    mmt.delete()
    Console().print(f"Successfully deleted {mmt.name}!")
