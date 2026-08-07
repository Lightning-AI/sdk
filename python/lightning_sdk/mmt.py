import warnings
from typing import TYPE_CHECKING, Dict, Optional, Protocol, Union, cast

from lightning_sdk.job import Job, JobDict
from lightning_sdk.status import Status

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

__all__ = ["MMT", "MMTMachine"]

_MMT_DEPRECATION_MESSAGE = (
    "lightning_sdk.MMT is deprecated. Use lightning_sdk.Job instead "
    "(Job.run(..., num_machines=N) for multi-machine jobs)."
)


class MMTMachine(Protocol):
    """A single machine in a multi-machine job."""

    @property
    def name(self) -> str:
        ...

    @property
    def machine(self) -> Union["Machine", str]:
        ...

    @property
    def artifact_path(self) -> Optional[str]:
        ...

    @property
    def status(self) -> Status:
        ...

    @property
    def resource_id(self) -> Optional[str]:
        ...

    @property
    def private_ip_address(self) -> Optional[str]:
        ...

    @property
    def placement_group_id(self) -> Optional[str]:
        ...

    @property
    def rank(self) -> Optional[int]:
        ...

    @property
    def logs(self) -> str:
        ...

    def dict(self) -> JobDict:
        ...


class MMT(Job):
    """Compatibility interface for multi-machine jobs.

    Multi-machine functionality is implemented by :class:`lightning_sdk.job.Job`.
    ``MMT`` is deprecated; use ``Job`` instead.
    """

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
        _num_machines: int = 2,
    ) -> None:
        warnings.warn(_MMT_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)
        try:
            super().__init__(
                name=name,
                teamspace=teamspace,
                org=org,
                user=user,
                _fetch_job=_fetch_job,
                # Default 2 forces the multi-machine API for lookup; real count is synced after fetch/attach.
                _num_machines=_num_machines,
            )
        except ValueError as ex:
            # Job.__init__ raises "Job {name} does not exist…" on 404; keep the MMT-specific
            # wording for that case only. Propagate teamspace/validation errors unchanged.
            if "does not exist in Teamspace" not in str(ex):
                raise
            resolved_teamspace = getattr(self, "_teamspace", None)
            teamspace_name = getattr(resolved_teamspace, "name", teamspace)
            raise ValueError(f"Multi-machine job {name} does not exist in Teamspace {teamspace_name}") from ex

    @classmethod
    def run(  # type: ignore[override]
        cls,
        name: str,
        num_machines: int,
        machine: Union["Machine", str],
        cloud: Optional[Union["CloudProvider", str]] = None,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Optional[str] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: Optional[str] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        reuse_snapshot: bool = True,
        placement_group_id: Optional[str] = None,
    ) -> "MMT":
        if num_machines <= 1:
            raise ValueError("Multi-Machine training cannot be run with less than 2 Machines")

        return cast(
            "MMT",
            super().run(
                name=name,
                machine=machine,
                cloud=cloud,
                command=command,
                studio=studio,
                image=image,
                teamspace=teamspace,
                org=org,
                user=user,
                env=env,
                interruptible=interruptible,
                image_credentials=image_credentials,
                cloud_account_auth=cloud_account_auth,
                entrypoint=entrypoint,
                path_mappings=path_mappings,
                max_runtime=max_runtime,
                reuse_snapshot=reuse_snapshot,
                placement_group_id=placement_group_id,
                num_machines=num_machines,
            ),
        )
