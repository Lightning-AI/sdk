from typing import Optional

from rich.console import Console
from rich.table import Table

from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lit_registry import LitRegistry


class _List(_TeamspacesMenu):
    """List resources on the Lightning AI platform."""

    def jobs(self, teamspace: Optional[str] = None) -> None:
        """List jobs for a given teamspace.

        Args:
            teamspace: the teamspace to list jobs from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.

        """
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)

        print("Available Jobs:\n" + "\n".join([j.name for j in resolved_teamspace.jobs]))

    def mmts(self, teamspace: Optional[str] = None) -> None:
        """List multi-machine jobs for a given teamspace.

        Args:
            teamspace: the teamspace to list jobs from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.

        """
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)

        print("Available MMTs:\n" + "\n".join([j.name for j in resolved_teamspace.multi_machine_jobs]))

    def containers(self, teamspace: Optional[str] = None) -> None:
        """Display the list of available containers.

        Args:
            teamspace: The teamspace to list containers from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
        """
        api = LitRegistry()
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)
        result = api.list_containers(teamspace=resolved_teamspace.name, org=resolved_teamspace.owner.name)
        table = Table(pad_edge=True, box=None)
        table.add_column("REPOSITORY")
        table.add_column("IMAGE ID")
        table.add_column("CREATED")
        for repo in result:
            table.add_row(repo["REPOSITORY"], repo["IMAGE ID"], repo["CREATED"])
        console = Console()
        console.print(table)
