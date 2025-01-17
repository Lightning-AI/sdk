from typing import Optional

from lightning_sdk.cli.jobs_menu import _JobsMenu
from lightning_sdk.cli.mmts_menu import _MMTsMenu
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu


class _Inspect(_TeamspacesMenu, _JobsMenu, _MMTsMenu):
    """Inspect resources of the Lightning AI platform to get additional details as JSON."""

    def job(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Inspect a job for further details as JSON.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        resolved_teamspace = self._resolve_teamspace(teamspace)
        resolved_job = self._resolve_job(name, teamspace=resolved_teamspace)

        print(resolved_job.json())

    def mmt(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Inspect a multi-machine job for further details as JSON.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        resolved_teamspace = self._resolve_teamspace(teamspace)
        resolved_mmt = self._resolve_mmt(name, teamspace=resolved_teamspace)

        print(resolved_mmt.json())
