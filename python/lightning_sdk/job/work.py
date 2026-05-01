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
        """Initialize a Work instance.

        Args:
            work_id: The unique ID of this work unit.
            job: The parent job that owns this work.
            teamspace: The teamspace the work belongs to.
        """
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
        """The unique ID of this work unit.

        Returns:
            str: The unique identifier of this work unit.
        """
        return self._guaranteed_work.id

    @property
    def name(self) -> str:
        """The name of this work unit.

        Returns:
            str: The display name of this work unit.
        """
        return self._job._name_filter(self._guaranteed_work.name)

    @property
    def machine(self) -> Union["Machine", str]:
        """The machine type this work unit is running on.

        Returns:
            Union[Machine, str]: The machine type, as a ``Machine`` enum or a raw string identifier.
        """
        return self._job_api.get_machine_from_work(
            self._guaranteed_work,
            org_id=_get_org_id(self._teamspace),
        )

    @property
    def artifact_path(self) -> Optional[str]:
        """Path to this work unit's artifacts in the distributed teamspace filesystem.

        Returns:
            Optional[str]: The filesystem path where this work unit's artifacts are stored.
        """
        return f"/teamspace/jobs/{self._job.name}/{self.name}"

    @property
    def status(self) -> "Status":
        """The current status of this work unit.

        Returns:
            Status: The current execution status of this work unit.
        """
        return self._job_api.get_status_from_work(self._latest_work)

    @property
    def logs(self) -> str:
        """The logs of the work.

        Returns:
            str: The full log output for this work unit.

        Raises:
            RuntimeError: If the work unit is still pending or running.
        """
        from lightning_sdk.status import Status

        if self.status not in (Status.Failed, Status.Completed, Status.Stopped):
            raise RuntimeError("Getting jobs logs while the job is pending or running is not supported yet!")

        return self._job_api.get_logs_finished(job_id=self._job._id, work_id=self._id, teamspace_id=self._teamspace.id)

    def dict(self) -> "MachineDict":
        """Dict representation of the work.

        Returns:
            MachineDict: A dictionary containing the work unit's name, status, and machine type.
        """
        return {
            "name": self.name,
            "status": self.status,
            "machine": self.machine,
        }
