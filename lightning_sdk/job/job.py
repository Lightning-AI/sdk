from functools import cached_property
from typing import Optional, Union

from lightning_sdk.api.job_api import JobApi
from lightning_sdk.job.work import Work
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.status import Status
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_teamspace


class Job:
    def __init__(
        self,
        name: str,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
    ) -> None:
        self._name = name

        self.teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)

        self._job_api = JobApi()

        try:
            self._job = self._job_api.get_job(name, self.teamspace.id)
        except ValueError as e:
            raise ValueError(f"Job {name} does not exist in Teamspace {self.teamspace.name}") from e

    @property
    def status(self) -> Status:
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
    def machine(self) -> Machine:
        return self.work.machine

    @property
    def id(self) -> str:
        return self._job.id

    @property
    def name(self) -> str:
        return self._job.name


def _internal_status_to_external_status(internal_status: str) -> Status:
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
