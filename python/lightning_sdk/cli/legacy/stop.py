from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.utils.resource_resolution import resolve_job, resolve_mmt, resolve_studio, resolve_teamspace


@click.group("stop")
def stop() -> None:
    """Stop resources on the Lightning AI platform."""


@stop.command("job")
@click.argument(
    "name",
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "Defaults to the current teamspace."
    ),
)
def job(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a job.

    Example:
      lightning stop job NAME

    NAME: the name of the job to stop.
    """
    job = resolve_job(name, resolve_teamspace(teamspace))

    job.stop()
    Console().print(f"Successfully stopped {job.name}!")


@stop.command("mmt")
@click.argument(
    "name",
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the multi-machine job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "Defaults to the current teamspace."
    ),
)
def mmt(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a multi-machine job.

    Example:
      lightning stop mmt NAME

    NAME: the name of the multi-machine job to stop.
    """
    mmt = resolve_mmt(name, resolve_teamspace(teamspace))

    mmt.stop()
    Console().print(f"Successfully stopped {mmt.name}!")


@stop.command("studio")
@click.argument(
    "name",
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the studio lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "Defaults to the current teamspace."
    ),
)
def studio(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a running studio.

    Example:
      lightning stop studio NAME

    NAME: the name of the studio to stop.
    """
    studio = resolve_studio(name, resolve_teamspace(teamspace))

    studio.stop()
    Console().print("Studio successfully stopped")
