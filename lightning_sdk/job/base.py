from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Union

from lightning_sdk.utils.resolve import _resolve_teamspace

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


class _BaseJob(ABC):
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
        self._teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        self._cluster = cluster
        self._name = name
        self._job = None

        if _fetch_job:
            self._update_internal_job()

    @classmethod
    def run(
        cls,
        name: str,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        teamspace: Union[str, "Teamspace"] = None,
        org: Union[str, "Organization"] = None,
        user: Union[str, "User"] = None,
        cluster: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
    ) -> "_BaseJob":
        # TODO: overwrite teamspace with studio teamspace if provided
        # TODO: resolve studio and support string studios
        # TODO: check if job already exists, then alter name
        # TODO: assertions for studio to be in teamspace and on cluster
        # TODO: if cluster is not provided use studio cluster if provided, otherwise use default cluster from teamspace
        inst = cls(name=name, teamspace=teamspace, org=org, user=user, cluster=cluster, _fetch_job=False)
        inst._submit(machine=machine, command=command, studio=studio, image=image, env=env, interruptible=interruptible)
        inst._update_internal_job()
        return inst

    @abstractmethod
    def _submit(
        self,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
    ) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def delete(self) -> None:
        pass

    @property
    @abstractmethod
    def status(self) -> "Status":
        pass

    @property
    @abstractmethod
    def machine(self) -> "Machine":
        pass

    @property
    @abstractmethod
    def artifact_path(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def snapshot_path(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def share_path(self) -> Optional[str]:
        pass

    @abstractmethod
    def _update_internal_job(self) -> None:
        pass

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace

    @property
    def cluster(self) -> Optional[str]:
        return self._cluster
