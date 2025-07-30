from typing import TYPE_CHECKING, Any, Optional, Protocol, Union

from lightning_sdk.api.job_api import JobApiV1
from lightning_sdk.utils.resolve import _get_org_id

if TYPE_CHECKING:
    from lightning_sdk.job.base import MachineDict
    from lightning_sdk.machine import Machine
    from lightning_sdk.status import Status
    from lightning_sdk.teamspace import Teamspace


class _WorkHolder(Protocol):
    @property
    def _id(self) -> str:
        ...

    @property
    def name(self) -> str:
        ...

    def _name_filter(self, name: str) -> str:
        ...


class Work:
    def __init__(self, work_id: str, job: _WorkHolder, teamspace: "Teamspace") -> None:
        self._id = work_id
        self._job = job
        self._teamspace = teamspace
        self._job_api = JobApiV1()
        self._work = None

    @property
    def _latest_work(self) -> Any:
        self._work = self._job_api.get_work(work_id=self._id, job_id=self._job._id, teamspace_id=self._teamspace.id)
        return self._work

    @property
    def _guaranteed_work(self) -> Any:
        if self._work is None:
            return self._latest_work

        return self._work

    @property
    def id(self) -> str:
        return self._guaranteed_work.id

    @property
    def name(self) -> str:
        return self._job._name_filter(self._guaranteed_work.name)

    @property
    def machine(self) -> Union["Machine", str]:
        return self._job_api.get_machine_from_work(
            self._guaranteed_work,
            org_id=_get_org_id(self._teamspace),
        )

    @property
    def artifact_path(self) -> Optional[str]:
        return f"/teamspace/jobs/{self._job.name}/{self.name}"

    @property
    def status(self) -> "Status":
        return self._job_api.get_status_from_work(self._latest_work)

    @property
    def logs(self) -> str:
        """The logs of the work."""
        from lightning_sdk.status import Status

        if self.status not in (Status.Failed, Status.Completed, Status.Stopped):
            raise RuntimeError("Getting jobs logs while the job is pending or running is not supported yet!")

        return self._job_api.get_logs_finished(job_id=self._job._id, work_id=self._id, teamspace_id=self._teamspace.id)

    def dict(self) -> "MachineDict":
        """Dict representation of the work."""
        return {
            "name": self.name,
            "status": self.status,
            "machine": self.machine,
        }
