from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lit_container import LitContainer
from lightning_sdk.studio import Studio


class _Delete(_JobAndMMTAction, _TeamspacesMenu):
    """Delete resources on the Lightning AI platform."""

    def container(self, container: str, teamspace: Optional[str] = None) -> None:
        """Delete a docker container.

        Args:
            container: The name of the container to delete.
            teamspace: The teamspace to delete the container from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
        """
        delete_container(container=container, teamspace=teamspace)

    def job(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Delete a job.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        job(name=name, teamspace=teamspace)

    def mmt(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Delete a multi-machine job.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        mmt(name=name, teamspace=teamspace)

    def studio(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Delete an existing studio.

        Args:
            name: The name of the studio to delete.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
                Note: This could delete your current studio if run without arguments.
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
        """
        studio(name=name, teamspace=teamspace)


@click.group()
def delete() -> None:
    """Delete resources on the Lightning AI platform."""


# @delete.command(name="container")
# @click.option("--container", help="The name of the container to delete.")
# @click.option("--teamspace", default=None, help=("The teamspace to delete the container from. "
#                                                  "Should be specified as {owner}/{name} "
#                                                  "If not provided, can be selected in an interactive menu."),)
def delete_container(container: str, teamspace: Optional[str] = None) -> None:
    """Delete the docker container CONTAINER."""
    api = LitContainer()
    menu = _TeamspacesMenu()
    resolved_teamspace = menu._resolve_teamspace(teamspace=teamspace)
    try:
        api.delete_container(container, resolved_teamspace.name, resolved_teamspace.owner.name)
        Console().print(f"Container {container} deleted successfully.")
    except Exception as e:
        raise StudioCliError(
            f"Could not delete container {container} from project {resolved_teamspace.name}: {e}"
        ) from None


# @delete.command(name="job")
# @click.option("--name", help="The name of the job to delete.")
# @click.option("--teamspace", default=None, help=("The teamspace to delete the job from. "
#                                                  "Should be specified as {owner}/{name} "
#                                                  "If not provided, can be selected in an interactive menu."),)
def job(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a job."""
    menu = _JobAndMMTAction()
    job = menu.job(name=name, teamspace=teamspace)

    job.delete()
    Console().print(f"Successfully deleted {job.name}!")


# @delete.command(name="mmt")
# @click.option("--name", help="The name of the multi-machine job to delete.")
# @click.option("--teamspace", default=None, help=("The teamspace to delete the job from. "
#                                                  "Should be specified as {owner}/{name} "
#                                                  "If not provided, can be selected in an interactive menu."),)
def mmt(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a multi-machine job."""
    menu = _JobAndMMTAction()
    mmt = menu.mmt(name=name, teamspace=teamspace)

    mmt.delete()
    Console().print(f"Successfully deleted {mmt.name}!")


# @delete.command(name="studio")
# @click.option("--name", help="The name of the studio to delete.")
# @click.option("--teamspace", default=None, help=("The teamspace to delete the studio from. "
#                                                  "Should be specified as {owner}/{name} "
#                                                  "If not provided, can be selected in an interactive menu."),)
def studio(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete an existing studio."""
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

    studio.delete()
    Console().print("Studio successfully deleted")
