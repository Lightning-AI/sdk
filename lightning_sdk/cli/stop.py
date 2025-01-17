from typing import Optional

from lightning_sdk.cli.job_and_mmt_action import _JobAndMMTAction


class _Stop(_JobAndMMTAction):
    """Stop resources on the Lightning AI platform."""

    def job(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Stop a job.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        job = super().job(name=name, teamspace=teamspace)

        job.stop()
        print(f"Successfully stopped {job.name}!")

    def mmt(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Stop a multi-machine job.

        Args:
            name: the name of the job. If not specified can be selected interactively.
            teamspace: the name of the teamspace the job lives in.
                Should be specified as {teamspace_owner}/{teamspace_name} (e.g my-org/my-teamspace).
                If not specified can be selected interactively.

        """
        mmt = super().mmt(name=name, teamspace=teamspace)

        mmt.stop()
        print(f"Successfully stopped {mmt.name}!")
