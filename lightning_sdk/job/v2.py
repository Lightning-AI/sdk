from typing import TYPE_CHECKING, Dict, Optional, Union

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
        raise NotImplementedError("Not implemented yet")

    def stop(self) -> None:
        raise NotImplementedError("Not implemented yet")

    def delete(self) -> None:
        raise NotImplementedError("Not implemented yet")

    @property
    def status(self) -> "Status":
        raise NotImplementedError("Not implemented yet")

    @property
    def artifact_path(self) -> Optional[str]:
        raise NotImplementedError("Not implemented yet")

    @property
    def snapshot_path(self) -> Optional[str]:
        raise NotImplementedError("Not implemented yet")

    @property
    def share_path(self) -> Optional[str]:
        raise NotImplementedError("Not implemented yet")

    def _update_internal_job(self) -> None:
        raise NotImplementedError("Not implemented yet")
