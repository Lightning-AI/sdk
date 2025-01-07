from typing import TYPE_CHECKING, Dict, Optional, Tuple, Union

from lightning_sdk.api.mmt_api import MMTApiV1
from lightning_sdk.job.v1 import _internal_status_to_external_status
from lightning_sdk.job.work import Work

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.mmt.base import _BaseMMT


class _MMTV1(_BaseMMT):
    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        self._job_api = MMTApiV1()
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
    ) -> "_MMTV1":
        if studio is None:
            raise ValueError("Studio is required for submitting jobs")
        if image is not None or image_credentials is not None or cloud_account_auth:
            raise ValueError("Image is not supported for submitting jobs")

        if artifacts_local is not None or artifacts_remote is not None:
            raise ValueError("Specifying how to persist artifacts is not yet supported with jobs")

        if env is not None:
            raise ValueError("Environment variables are not supported for submitting jobs")
        if command is None:
            raise ValueError("Command is required for submitting multi-machine jobs")

        _submitted = self._job_api.submit_job(
            name=self._name,
            num_machines=num_machines,
            command=command,
            studio_id=studio._studio.id,
            teamspace_id=self._teamspace.id,
            cloud_account=cloud_account or "",
            machine=machine,
            interruptible=interruptible,
            strategy="parallel",
        )

        self._name = _submitted.name
        self._job = _submitted
        return self

    def _update_internal_job(self) -> None:
        try:
            self._job = self._job_api.get_job(self._name, self.teamspace.id)
        except ValueError as e:
            raise ValueError(f"Job {self._name} does not exist in Teamspace {self.teamspace.name}") from e

    @property
    def machines(self) -> Tuple["Work", ...]:
        works = self._job_api.list_works(self._guaranteed_job.id, self.teamspace.id)

        return tuple(Work(w.id, self, self.teamspace) for w in works)

    def stop(self) -> None:
        self._job_api.stop_job(self._guaranteed_job.id, self.teamspace.id)

    def delete(self) -> None:
        self._job_api.delete_job(self._guaranteed_job.id, self.teamspace.id)

    @property
    def status(self) -> "Status":
        try:
            status = self._job_api.get_job_status(self._job.id, self.teamspace.id)
            return _internal_status_to_external_status(status)
        except Exception:
            raise RuntimeError(
                f"MMT {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    @property
    def artifact_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self.name}"

    @property
    def snapshot_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self.name}/snapshot"

    @property
    def machine(self) -> "Machine":
        return self.machines[0].machine

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace

    # the following and functions are solely to make the Work class function
    @property
    def _id(self) -> str:
        return self._guaranteed_job.id

    def _name_filter(self, name: str) -> str:
        return name.replace("root.", "")
