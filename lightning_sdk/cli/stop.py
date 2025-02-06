from typing import Optional

from lightning_sdk.cli.job_and_mmt_action import _JobAndMMTAction
from lightning_sdk.studio import Studio


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

    def studio(self, name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
        """Stop a running studio.

        Args:
            name: The name of the studio to stop.
                If not specified, tries to infer from the environment (e.g. when run from within a Studio.)
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

        studio.stop()
        print("Studio successfully stopped")
