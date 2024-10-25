from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.job.base import _BaseJob

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


class _JobV2(_BaseJob):
    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace"] = None,
        org: Union[str, "Organization"] = None,
        user: Union[str, "User"] = None,
        cluster: Optional[str] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        self._job_api = JobApiV2()
        super().__init__(name=name, teamspace=teamspace, org=org, user=user, cluster=cluster, _fetch_job=_fetch_job)

    def _submit(
        self,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
    ) -> None:
        # Command is required if Studio is provided to know what to run
        # Image is mutually exclusive with Studio
        # Command is optional for Image
        # Either image or studio must be provided
        if studio is not None:
            studio_id = studio._studio.id
            if image is not None:
                raise ValueError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )
            if command is None:
                raise ValueError("command is required when using a studio")
        else:
            studio_id = None
            if image is None:
                raise ValueError("either image or studio must be provided")

        submitted = self._job_api.submit_job(
            name=self.name,
            command=command,
            cluster_id=self._cluster,
            teamspace_id=self._teamspace.id,
            studio_id=studio_id,
            image=image,
            machine=machine,
            interruptible=interruptible,
            env=env,
        )
        self._job = submitted
        self._name = submitted.name

    def stop(self) -> None:
        if self._job is None:
            self._update_internal_job()

        self._job_api.stop_job(job_id=self._job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        if self._job is None:
            self._update_internal_job()

        self._job_api.delete_job(
            job_id=self._job.id, teamspace_id=self._teamspace.id, cloudspace_id=self._job.spec.cloudspace_id
        )

    @property
    def _latest_job(self) -> Any:
        """Guarantees to fetch the latest version of a job before returning it."""
        self._update_internal_job()
        return self._job

    @property
    def _guaranteed_job(self) -> Any:
        """Guarantees that the job was fetched at some point before returning it.

        Doesn't guarantee to have the lastest version of the job. Use _latest_job for that.
        """
        if getattr(self, "_job", None) is None:
            self._update_internal_job()

        return self._job

    @property
    def status(self) -> "Status":
        return self._job_api._job_state_to_external(self._latest_job.state)

    @property
    def machine(self) -> "Machine":
        # only fetch the job it it hasn't been fetched yet as machine cannot change over time
        return self._job_api._get_job_machine_from_spec(self._guaranteed_job.spec)

    @property
    def artifact_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self._guaranteed_job.name}/artifacts"

    @property
    def snapshot_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self._guaranteed_job.name}/snapshot"

    @property
    def share_path(self) -> Optional[str]:
        raise NotImplementedError("Not implemented yet")

    def _update_internal_job(self) -> None:
        if getattr(self, "_job", None) is None:
            self._job = self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id)
            return

        self._job = self._job_api.get_job(job_id=self._job.id, teamspace_id=self._teamspace.id)
