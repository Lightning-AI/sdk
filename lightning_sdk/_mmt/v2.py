from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from lightning_sdk.api.mmt_api import MMTApi

if TYPE_CHECKING:
    from lightning_sdk.job.job import Job
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk._mmt.base import _BaseMMT


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
        self._job_api = MMTApi()
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
        cluster: Optional[str] = None,
        image_credentials: Optional[str] = None,
        cluster_auth: bool = False,
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
            cluster_id=cluster,
            teamspace_id=self._teamspace.id,
            studio_id=studio_id,
            image=image,
            machine=machine,
            interruptible=interruptible,
            env=env,
            image_credentials=image_credentials,
            cluster_auth=cluster_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )
        self._job = submitted
        self._name = submitted.name
        return self

    @property
    def machines(self) -> Tuple["Job", ...]:
        raise NotImplementedError

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
    def _guaranteed_job(self) -> Any:
        """Guarantees that the job was fetched at some point before returning it.

        Doesn't guarantee to have the lastest version of the job. Use _latest_job for that.
        """
        if getattr(self, "_job", None) is None:
            self._update_internal_job()

        return self._job

    @property
    def status(self) -> "Status":
        # TODO: Should this rather be a list of states from the individual machines?
        return self._job_api._job_state_to_external(self._latest_job.desired_state)

    @property
    def artifact_path(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def snapshot_path(self) -> Optional[str]:
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
