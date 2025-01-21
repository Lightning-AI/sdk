from typing import Optional

from rich.console import Console
from rich.table import Table

from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lit_container import LitContainer


class _List(_TeamspacesMenu):
    """List resources on the Lightning AI platform."""

    def jobs(self, teamspace: Optional[str] = None) -> None:
        """List jobs for a given teamspace.

        Args:
            teamspace: the teamspace to list jobs from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.

        """
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)

        jobs = resolved_teamspace.jobs

        table = Table(
            pad_edge=True,
        )
        table.add_column("Name")
        table.add_column("Teamspace")
        table.add_column("Studio")
        table.add_column("Image")
        table.add_column("Status")
        table.add_column("Machine")
        table.add_column("Total Cost")
        for j in jobs:
            # we know we just fetched these, so no need to refetch
            j._prevent_refetch_latest = True
            j._internal_job._prevent_refetch_latest = True

            studio = j.studio
            table.add_row(
                j.name,
                f"{j.teamspace.owner.name}/{j.teamspace.name}",
                studio.name if studio else None,
                j.image,
                str(j.status),
                str(j.machine),
                f"{j.total_cost:.3f}",
            )

        console = Console()
        console.print(table)

    def mmts(self, teamspace: Optional[str] = None) -> None:
        """List multi-machine jobs for a given teamspace.

        Args:
            teamspace: the teamspace to list jobs from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.

        """
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)

        jobs = resolved_teamspace.multi_machine_jobs

        table = Table(pad_edge=True)
        table.add_column("Name")
        table.add_column("Teamspace")
        table.add_column("Studio")
        table.add_column("Image")
        table.add_column("Status")
        table.add_column("Machine")
        table.add_column("Num Machines")
        table.add_column("Total Cost")
        for j in jobs:
            # we know we just fetched these, so no need to refetch
            j._prevent_refetch_latest = True
            j._internal_job._prevent_refetch_latest = True

            studio = j.studio
            table.add_row(
                j.name,
                f"{j.teamspace.owner.name}/{j.teamspace.name}",
                studio.name if studio else None,
                j.image,
                str(j.status),
                str(j.machine),
                str(j.num_machines),
                str(j.total_cost),
            )

        console = Console()
        console.print(table)

    def containers(self, teamspace: Optional[str] = None) -> None:
        """Display the list of available containers.

        Args:
            teamspace: The teamspace to list containers from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
        """
        api = LitContainer()
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
