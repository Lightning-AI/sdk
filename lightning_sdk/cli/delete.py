from typing import Optional

from lightning_sdk.cli.exceptions import StudioCliError
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lit_container import LitContainer


class _Delete(_TeamspacesMenu):
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
