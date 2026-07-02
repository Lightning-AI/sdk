"""MMT stop command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("stop", cls=LightningCommand)
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the multi-machine job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def stop_mmt(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a multi-machine job."""
    menu = _JobAndMMTAction()
    mmt = menu.mmt(name=name, teamspace=teamspace)
    mmt.stop()
    Console().print(f"Successfully stopped {mmt.name}!")
