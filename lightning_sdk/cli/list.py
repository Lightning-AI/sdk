from typing import Optional

from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu


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
