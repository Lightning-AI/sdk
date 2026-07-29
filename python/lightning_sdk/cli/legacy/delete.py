from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace
from lightning_sdk.deployment import Deployment
from lightning_sdk.lit_container import LitContainer


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
        "Defaults to the current teamspace."
    ),
)
def container(name: str, teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """Delete the docker container NAME."""
    api = LitContainer()
    resolved_teamspace = resolve_teamspace(teamspace)
    try:
        api.delete_container(name, resolved_teamspace.name, resolved_teamspace.owner.name)
        if as_json:
            echo_json({"name": name, "deleted": True})
            return
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
        "Defaults to the current teamspace."
    ),
)
def studio(name: str, teamspace: Optional[str] = None) -> None:
    """Delete an existing studio.

    Example:
      lightning delete studio NAME

    NAME: the name of the studio to delete
    """
    studio = resolve_studio(name, resolve_teamspace(teamspace))

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
        "Defaults to the current teamspace."
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
