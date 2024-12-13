from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from lightning_sdk.job.job import Job
    from lightning_sdk.machine import Machine
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace

from lightning_sdk._mmt.base import _BaseMMT


class _MMTV1(_BaseMMT):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

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
    ) -> None:
        raise NotImplementedError

    @property
    def machines(self) -> Tuple["Job", ...]:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def delete(self) -> None:
        raise NotImplementedError

    @property
    def status(self) -> "Status":
        raise NotImplementedError

    @property
    def artifact_path(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def snapshot_path(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def machine(self) -> "Machine":
        raise NotImplementedError

    def _update_internal_job(self) -> None:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace
