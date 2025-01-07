from typing import TYPE_CHECKING, Any, Dict, Optional, Protocol, Tuple, Union

from lightning_sdk.job.job import _has_jobs_v2
from lightning_sdk.mmt.base import _BaseMMT
from lightning_sdk.mmt.v1 import _MMTV1
from lightning_sdk.mmt.v2 import _MMTV2

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


class MMTMachine(Protocol):
    """A single machine in multi-machine training."""

    @property
    def name(self) -> str:
        ...

    @property
    def machine(self) -> "Machine":
        ...

    @property
    def artifact_path(self) -> Optional[str]:
        ...

    @property
    def status(self) -> "Status":
        ...


class MMT(_BaseMMT):
    _force_v1: (
        bool
    ) = False  # required for studio plugin still working correctly as v2 currently does not support the studio env

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        internal_mmt_cls = _MMTV2 if _has_jobs_v2() and not self._force_v1 else _MMTV1

        self._internal_mmt = internal_mmt_cls(
            name=name,
            teamspace=teamspace,
            org=org,
            user=user,
            _fetch_job=_fetch_job,
        )

    @classmethod
    def run(
        cls,
        name: str,
        num_machines: int,
        machine: "Machine",
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Union[str, None] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> "MMT":
        ret_val = super().run(
            name=name,
            num_machines=num_machines,
            machine=machine,
            command=command,
            studio=studio,
            image=image,
            teamspace=teamspace,
            org=org,
            user=user,
            cloud_account=cloud_account,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            cluster=cluster,  # deprecated in favor of cloud_account
        )
        # required for typing with "Job"
        assert isinstance(ret_val, cls)
        return ret_val

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
    ) -> "MMT":
        self._job = self._internal_mmt._submit(
            num_machines=num_machines,
            machine=machine,
            cloud_account=cloud_account,
            command=command,
            studio=studio,
            image=image,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )
        return self

    def stop(self) -> None:
        return self._internal_mmt.stop()

    def delete(self) -> None:
        return self._internal_mmt.delete()

    @property
    def status(self) -> "Status":
        return self._internal_mmt.status

    @property
    def machines(self) -> Tuple[MMTMachine, ...]:
        return self._internal_mmt.machines

    @property
    def machine(self) -> "Machine":
        return self._internal_mmt.machine

    @property
    def artifact_path(self) -> Optional[str]:
        return self._internal_mmt.artifact_path

    @property
    def snapshot_path(self) -> Optional[str]:
        return self._internal_mmt.snapshot_path

    @property
    def share_path(self) -> Optional[str]:
        return None

    def _update_internal_job(self) -> None:
        return self._internal_mmt._update_internal_job()

    @property
    def name(self) -> str:
        return self._internal_mmt.name

    @property
    def teamspace(self) -> "Teamspace":
        return self._internal_mmt._teamspace

    @property
    def cloud_account(self) -> Optional[str]:
        return self._internal_mmt.cloud_account

    def __getattr__(self, key: str) -> Any:
        """Forward the attribute lookup to the internal job implementation."""
        try:
            return getattr(super(), key)
        except AttributeError:
            return getattr(self._internal_mmt, key)

    @property
    def _guaranteed_job(self) -> Any:
        return self._internal_mmt._guaranteed_job
