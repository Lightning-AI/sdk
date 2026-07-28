from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_mmt, resolve_teamspace


@click.group(name="inspect")
def inspect() -> None:
    """Inspect resources of the Lightning AI platform to get additional details as JSON."""


@inspect.command(name="job")
@click.option("--name", default=None, help="the name of the job to inspect.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in."
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "Defaults to the current teamspace."
    ),
)
def job(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Inspect a job for further details as JSON."""
    Console().print(resolve_job(name, resolve_teamspace(teamspace)).json())


@inspect.command(name="mmt")
@click.option("--name", default=None, help="the name of the multi-machine job to inspect.")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in."
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "Defaults to the current teamspace."
    ),
)
def mmt(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Inspect a multi-machine job for further details as JSON."""
    Console().print(resolve_mmt(name, resolve_teamspace(teamspace)).json())
