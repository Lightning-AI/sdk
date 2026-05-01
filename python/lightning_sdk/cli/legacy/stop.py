from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.studio import Studio


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
        "If not specified can be selected interactively."
    ),
)
def job(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a job.

    Example:
      lightning stop job NAME

    NAME: the name of the job to stop.
    """
    menu = _JobAndMMTAction()
    job = menu.job(name=name, teamspace=teamspace)

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
        "If not specified can be selected interactively."
    ),
)
def mmt(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a multi-machine job.

    Example:
      lightning stop mmt NAME

    NAME: the name of the multi-machine job to stop.
    """
    menu = _JobAndMMTAction()
    mmt = menu.mmt(name=name, teamspace=teamspace)

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
        "If not specified can be selected interactively."
    ),
)
def studio(name: str, teamspace: Optional[str] = None) -> None:
    """Stop a running studio.

    Example:
      lightning stop studio NAME

    NAME: the name of the studio to stop.
    """
    if teamspace is not None:
        ts_splits = teamspace.split("/")
        if len(ts_splits) != 2:
            raise ValueError(f"Teamspace should be of format <OWNER>/<TEAMSPACE_NAME> but got {teamspace}")
        owner, teamspace = ts_splits
    else:
        owner, teamspace = None, None

    try:
        studio = Studio(name=name, teamspace=teamspace, org=owner, user=None, create_ok=False)
    except (RuntimeError, ValueError, ApiException):
        studio = Studio(name=name, teamspace=teamspace, org=None, user=owner, create_ok=False)

    studio.stop()
    Console().print("Studio successfully stopped")
