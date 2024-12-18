from abc import abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Tuple, Union

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.job.base import _BaseJob
from lightning_sdk.job.job import Job
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster


class _BaseMMT(_BaseJob):
    @classmethod
    def run(
        cls,
        name: str,
        machine: "Machine",
        num_machines: int,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Optional[str] = None,
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
    ) -> "_BaseMMT":
        from lightning_sdk.studio import Studio

        cloud_account = _resolve_deprecated_cluster(cloud_account, cluster)

        if num_machines <= 1:
            raise ValueError("Multi-Machine training cannot be run with less than 2 Machines")

        if not name:
            raise ValueError("A job needs to have a name!")

        if image is None:
            if not isinstance(studio, Studio):
                studio = Studio(
                    name=studio, teamspace=teamspace, org=org, user=user, cloud_account=cloud_account, create_ok=False
                )

            # studio is a Studio instance at this point
            if teamspace is None:
                teamspace = studio.teamspace
            else:
                teamspace_name = teamspace if isinstance(teamspace, str) else teamspace.name

                if studio.teamspace.name != teamspace_name:
                    raise ValueError(
                        "Studio teamspace does not match provided teamspace. "
                        "Can only run jobs with Studio envs in the teamspace of that Studio."
                    )

            if cloud_account is None:
                cloud_account = studio.cloud_account

            if cloud_account != studio.cloud_account:
                raise ValueError(
                    "Studio cloud_account does not match provided cloud_account. "
                    "Can only run jobs with Studio envs in the same cloud_account."
                )

            if image_credentials is not None:
                raise ValueError("image_credentials is only supported when using a custom image")

            if cloud_account_auth:
                raise ValueError("cloud_account_auth is only supported when using a custom image")

            if artifacts_local is not None or artifacts_remote is not None:
                raise ValueError(
                    "Specifying artifacts persistence is supported for docker images only. "
                    "Other jobs will automatically persist artifacts to the teamspace distributed filesystem."
                )

        else:
            if studio is not None:
                raise RuntimeError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )

            # they either need to specified both or none of them
            if bool(artifacts_local) != bool(artifacts_remote):
                raise ValueError("Artifact persistence requires both artifacts_local and artifacts_remote to be set")

            if artifacts_remote and len(artifacts_remote.split(":")) != 3:
                raise ValueError(
                    "Artifact persistence requires exactly three arguments separated by colon of kind "
                    f"<CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>, got {artifacts_local}"
                )

        inst = cls(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=False)
        inst._submit(
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
        return inst

    @abstractmethod
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
    ) -> None:
        """Submits a job and updates the internal _job attribute as well as the _name attribute."""

    @property
    @abstractmethod
    def machines(self) -> Tuple["Job", ...]:
        pass

    @property
    @abstractmethod
    def machine(self) -> "Machine":
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
    def artifact_path(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def snapshot_path(self) -> Optional[str]:
        pass

    @property
    def share_path(self) -> Optional[str]:
        return None

    @abstractmethod
    def _update_internal_job(self) -> None:
        pass

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace
