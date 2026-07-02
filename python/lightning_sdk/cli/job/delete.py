"""Job delete command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("delete", cls=LightningCommand)
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
def delete_job(name: str, teamspace: Optional[str] = None) -> None:
    """Delete a job."""
    menu = _JobAndMMTAction()
    job = menu.job(name=name, teamspace=teamspace)
    job.delete()
    Console().print(f"Successfully deleted {job.name}!")
