from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.deployment import Deployment
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lit_container import LitContainer
from lightning_sdk.studio import Studio


@click.group()
def delete() -> None:
    """Delete resources on the Lightning AI platform."""


@delete.command(name="container")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the container from. "
        "Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
def container(name: str, teamspace: Optional[str] = None) -> None:
    """Delete the docker container NAME."""
    api = LitContainer()
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)
    try:
        api.delete_container(name, resolved_teamspace.name, resolved_teamspace.owner.name)
        Console().print(f"Container {name} deleted successfully.")
    except Exception as e:
        raise StudioCliError(f"Could not delete container {name} from project {resolved_teamspace.name}: {e}") from None


@delete.command(name="studio")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the studio from. "
        "Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
def studio(name: str, teamspace: Optional[str] = None) -> None:
    """Delete an existing studio.

    Example:
      lightning delete studio NAME

    NAME: the name of the studio to delete
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

    studio.delete()
    Console().print("Studio successfully deleted")


@delete.command(name="deployment")
@click.argument("name")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace to delete the deployment from. "
        "Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
def deployment(name: str, teamspace: Optional[str] = None) -> None:
    """Delete an existing deployment.

    Example:
      lightning delete deployment NAME

    NAME: the name of the deployment to delete
    """
    api = Deployment(
        name=name,
        teamspace=teamspace,
    )

    try:
        api.delete()
        Console().print(f"Deployment {name} deleted successfully.")
    except Exception as e:
        raise StudioCliError(f"Could not delete deployment {name} from project {teamspace}: {e}") from None
