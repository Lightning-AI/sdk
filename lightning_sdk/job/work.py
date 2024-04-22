from typing import TYPE_CHECKING

from lightning_sdk.api.job_api import JobApi
from lightning_sdk.machine import Machine
from lightning_sdk.teamspace import Teamspace

if TYPE_CHECKING:
    from lightning_sdk.job.job import Job


class Work:
    def __init__(self, work_id: str, job: "Job", teamspace: Teamspace) -> None:
        self._id = work_id
        self._job = job
        self._teamspace = teamspace
        self._job_api = JobApi()
        self._work = self._job_api.get_work(work_id=work_id, job_id=job.id, teamspace_id=teamspace.id)

    @property
    def id(self) -> str:
        return self._work.id

    @property
    def name(self) -> str:
        return self._job._name_filter(self._work.name)

    @property
    def machine(self) -> Machine:
        return self._job_api.get_machine_from_work(self._work)
