from typing import TYPE_CHECKING, Dict, Optional, Union

from lightning_sdk.api.job_api import JobApiV1
from lightning_sdk.job.base import _BaseJob
from lightning_sdk.status import Status

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from functools import cached_property

from lightning_sdk.job.work import Work


class _JobV1(_BaseJob):
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
        self._job_api = JobApiV1()
        super().__init__(name=name, teamspace=teamspace, org=org, user=user, cluster=cluster, _fetch_job=_fetch_job)

    @classmethod
    def run(
        cls,
        name: str,
        machine: "Machine",
        command: str,
        studio: "Studio",
        teamspace: Union[str, "Teamspace"] = None,
        org: Union[str, "Organization"] = None,
        user: Union[str, "User"] = None,
        cluster: Optional[str] = None,
        interruptible: bool = False,
    ) -> "_BaseJob":
        return super().run(
            name=name,
            machine=machine,
            command=command,
            studio=studio,
            image=None,
            teamspace=teamspace,
            org=org,
            user=user,
            cluster=cluster,
            env=None,
            interruptible=interruptible,
        )

    def _submit(
        self,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
    ) -> None:
        if studio is None:
            raise ValueError("Studio is required for submitting jobs")

        if image is not None:
            raise ValueError("Image is not supported for submitting jobs")

        if env is not None:
            raise ValueError("Environment variables are not supported for submitting jobs")

        if command is None:
            raise ValueError("Command is required for submitting jobs")

        # TODO: add support for empty names (will give an empty string)

        _submitted = self._job_api.submit_job(
            name=self._name,
            command=command,
            studio_id=studio._studio.id,
            teamspace_id=self._teamspace.id,
            cluster_id=self._cluster,
            machine=machine,
            interruptible=interruptible,
        )
        self._name = _submitted.name
        self._job = _submitted

    def _update_internal_job(self) -> None:
        try:
            self._job = self._job_api.get_job(self._name, self.teamspace.id)
        except ValueError as e:
            raise ValueError(f"Job {self._name} does not exist in Teamspace {self.teamspace.name}") from e

    @property
    def status(self) -> "Status":
        try:
            status = self._job_api.get_job_status(self._job.id, self.teamspace.id)
            return _internal_status_to_external_status(status)
        except Exception:
            raise RuntimeError(
                f"Job {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    def stop(self) -> None:
        if self.status in (Status.Stopped, Status.Failed):
            return None

        return self._job_api.stop_job(self._job.id, self.teamspace.id)

    def delete(self) -> None:
        self._job_api.delete_job(self._job.id, self.teamspace.id)

    def _name_filter(self, orig_name: str) -> str:
        return orig_name.replace("root.", "")

    @cached_property
    def work(self) -> Work:
        _work = self._job_api.list_works(self._job.id, self.teamspace.id)
        if len(_work) == 0:
            raise ValueError("No works found for job")
        return Work(_work[0].id, self, self.teamspace)

    @property
    def machine(self) -> "Machine":
        return self.work.machine

    @property
    def id(self) -> str:
        return self._job.id

    @property
    def name(self) -> str:
        return self._job.name

    @property
    def artifact_path(self) -> Optional[str]:
        return self.work.artifact_path

    @property
    def snapshot_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self.name}/snapshot"

    @property
    def share_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self.name}/share"


def _internal_status_to_external_status(internal_status: str) -> "Status":
    """Converts internal status strings from HTTP requests to external enums."""
    return {
        # don't get a status if no instance alive
        None: Status.Stopped,
        # TODO: should we have deleted in here?
        "LIGHTNINGAPP_INSTANCE_STATE_UNSPECIFIED": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_IMAGE_BUILDING": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_NOT_STARTED": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_PENDING": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_RUNNING": Status.Running,
        "LIGHTNINGAPP_INSTANCE_STATE_FAILED": Status.Failed,
        "LIGHTNINGAPP_INSTANCE_STATE_STOPPED": Status.Stopped,
        "LIGHTNINGAPP_INSTANCE_STATE_COMPLETED": Status.Completed,
    }[internal_status]
