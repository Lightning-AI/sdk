from typing import Optional

from rich.console import Console

from lightning_sdk.cli.job_and_mmt_action import _JobAndMMTAction


class _Inspect(_JobAndMMTAction):
    """Inspect resources of the Lightning AI platform to get additional details as JSON."""

    def job(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Inspect a job for further details as JSON.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        (super().job(name=name, teamspace=teamspace).json())

    def mmt(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Inspect a multi-machine job for further details as JSON.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        Console().print(super().mmt(name=name, teamspace=teamspace).json())
