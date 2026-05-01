"""MMT inspect command."""

from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction


@click.command("inspect")
@click.option("--name", default=None, help="the name of the job. If not specified can be selected interactively.")
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
    menu = _JobAndMMTAction()
    Console().print(menu.mmt(name=name, teamspace=teamspace).json())
