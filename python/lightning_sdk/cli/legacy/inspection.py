from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction


@click.group(name="inspect")
def inspect() -> None:
    """Inspect resources of the Lightning AI platform to get additional details as JSON."""


@inspect.command(name="job")
@click.option("--name", default=None, help="the name of the job. If not specified can be selected interactively.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in."
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def job(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Inspect a job for further details as JSON."""
    menu = _JobAndMMTAction()
    Console().print(menu.job(name=name, teamspace=teamspace).json())


@inspect.command(name="mmt")
@click.option("--name", default=None, help="the name of the job. If not specified can be selected interactively.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in."
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def mmt(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Inspect a multi-machine job for further details as JSON."""
    menu = _JobAndMMTAction()
    Console().print(menu.mmt(name=name, teamspace=teamspace).json())
