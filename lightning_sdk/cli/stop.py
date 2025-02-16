from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.studio import Studio


@click.group("stop")
def stop() -> None:
    """Stop resources on the Lightning AI platform."""


@stop.command("job")
@click.option(
    "--name",
    default=None,
    help="the name of the job. If not specified can be selected interactively.",
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def job(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a job."""
    menu = _JobAndMMTAction()
    job = menu.job(name=name, teamspace=teamspace)

    job.stop()
    Console().print(f"Successfully stopped {job.name}!")


@stop.command("mmt")
@click.option(
    "--name",
    default=None,
    help="the name of the multi-machine job. If not specified can be selected interactively.",
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the multi-machine job lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def mmt(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a multi-machine job."""
    menu = _JobAndMMTAction()
    mmt = menu.mmt(name=name, teamspace=teamspace)

    mmt.stop()
    Console().print(f"Successfully stopped {mmt.name}!")


@stop.command("studio")
@click.option(
    "--name",
    default=None,
    help="the name of the studio. If not specified can be selected interactively.",
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the name of the teamspace the studio lives in. "
        "Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace). "
        "If not specified can be selected interactively."
    ),
)
def studio(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a running studio."""
    if teamspace is not None:
        ts_splits = teamspace.split("/")
        if len(ts_splits) != 2:
            raise ValueError(f"Teamspace should be of format <OWNER>/<TEAMSPACE_NAME> but got {teamspace}")
        owner, teamspace = ts_splits
    else:
        owner, teamspace = None, None

    try:
        studio = Studio(name=name, teamspace=teamspace, org=owner, user=None, create_ok=False)
    except (RuntimeError, ValueError):
        studio = Studio(name=name, teamspace=teamspace, org=None, user=owner, create_ok=False)

    studio.stop()
    Console().print("Studio successfully stopped")
