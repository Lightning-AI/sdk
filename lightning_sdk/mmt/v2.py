from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from lightning_sdk.api.mmt_api import MMTApiV2

if TYPE_CHECKING:
    from lightning_sdk.job.job import Job
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.mmt.base import _BaseMMT


class _MMTV2(_BaseMMT):
    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        self._job_api = MMTApiV2()
        super().__init__(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=_fetch_job)

    def _submit(
        self,
        num_machines: int,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
    ) -> "_MMTV2":
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
            num_machines=num_machines,
            command=command,
            cloud_account=cloud_account,
            teamspace_id=self._teamspace.id,
            studio_id=studio_id,
            image=image,
            machine=machine,
            interruptible=interruptible,
            env=env,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )
        self._job = submitted
        self._name = submitted.name
        return self

    @property
    def machines(self) -> Tuple["Job", ...]:
        from lightning_sdk.job import Job

        return tuple(
            Job(name=j.name, teamspace=self.teamspace)
            for j in self._job_api.list_mmt_subjobs(self._guaranteed_job.id, self.teamspace.id)
        )

    def stop(self) -> None:
        self._job_api.stop_job(job_id=self._guaranteed_job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        self._job_api.delete_job(
            job_id=self._guaranteed_job.id,
            teamspace_id=self._teamspace.id,
        )

    @property
    def _latest_job(self) -> Any:
        """Guarantees to fetch the latest version of a job before returning it."""
        self._update_internal_job()
        return self._job

    @property
    def status(self) -> "Status":
        return self._job_api._job_state_to_external(self._latest_job.state)

    @property
    def artifact_path(self) -> Optional[str]:
        # TODO: Since grouping for those is not done yet on the BE, we cannot yet have a unified link here
        raise NotImplementedError

    @property
    def snapshot_path(self) -> Optional[str]:
        # TODO: Since grouping for those is not done yet on the BE, we cannot yet have a unified link here
        raise NotImplementedError

    @property
    def machine(self) -> "Machine":
        return self._job_api._get_job_machine_from_spec(self._guaranteed_job.spec)

    def _update_internal_job(self) -> None:
        if getattr(self, "_job", None) is None:
            self._job = self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id)
            return

        self._job = self._job_api.get_job(job_id=self._job.id, teamspace_id=self._teamspace.id)

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace
