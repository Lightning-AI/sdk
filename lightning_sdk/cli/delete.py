from typing import Optional

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
        api = LitContainer()
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)
        try:
            api.delete_container(container, resolved_teamspace.name, resolved_teamspace.owner.name)
            print(f"Container {container} deleted successfully.")
        except Exception as e:
            raise StudioCliError(
                f"Could not delete container {container} from project {resolved_teamspace.name}: {e}"
            ) from None

    def job(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Delete a job.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        job = super().job(name=name, teamspace=teamspace)

        job.delete()
        print(f"Successfully deleted {job.name}!")

    def mmt(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Delete a multi-machine job.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        mmt = super().mmt(name=name, teamspace=teamspace)

        mmt.delete()
        print(f"Successfully deleted {mmt.name}!")

    def studio(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Delete an existing studio.

        Args:
            name: The name of the studio to delete.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
                Note: This could delete your current studio if run without arguments.
            teamspace: The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
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
        except (RuntimeError, ValueError):
            studio = Studio(name=name, teamspace=teamspace, org=None, user=owner, create_ok=False)

        studio.delete()
        print("Studio successfully deleted")
