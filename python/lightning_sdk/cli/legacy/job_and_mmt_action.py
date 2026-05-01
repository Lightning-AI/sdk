from typing import Optional

from lightning_sdk.cli.legacy.jobs_menu import _JobsMenu
from lightning_sdk.cli.legacy.mmts_menu import _MMTsMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.job import Job
from lightning_sdk.mmt import MMT


class _JobAndMMTAction(TeamspacesMenu, _JobsMenu, _MMTsMenu):
    """Inspect resources of the Lightning AI platform to get additional details as JSON."""

    def job(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> Job:
        """Fetch a job for further processing.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        resolved_teamspace = self(teamspace)
        return self._resolve_job(name, teamspace=resolved_teamspace)

    def mmt(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> MMT:
        """Fetch a multi-machine job for further processing.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        resolved_teamspace = self(teamspace)
        return self._resolve_mmt(name, teamspace=resolved_teamspace)
