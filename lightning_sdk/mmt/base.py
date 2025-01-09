from abc import abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Protocol, Tuple, Union

if TYPE_CHECKING:
    from lightning_sdk.machine import Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.job.base import _BaseJob
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster


class MMTMachine(Protocol):
    """A single machine in multi-machine training."""

    @property
    def name(self) -> str:
        """The Name of the individual machine. Usually corresponds to the rank."""
        ...

    @property
    def machine(self) -> "Machine":
        """The actual machine type this node is running on."""
        ...

    @property
    def artifact_path(self) -> Optional[str]:
        """The path to the artifacts of this job."""
        ...

    @property
    def status(self) -> "Status":
        """The status of this job."""
        ...

    @property
    def logs(self) -> str:
        """The logs of the given machine."""
        ...


class _BaseMMT(_BaseJob):
    """Base interface to all job types."""

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
        """Run async workloads using a docker image across multiple machines.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            num_machine: The number of machines to run on.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
            org: The organization owning the teamspace (if any). Defaults to the current organization.
            user: The user owning the teamspace (if any). Defaults to the current user.
            cloud_account: The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                If not provided will fall back to the teamspaces default cloud account.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            artifacts_local: The path of inside the docker container, you want to persist images from.
                CAUTION: When setting this to "/", it will effectively erase your container.
                Only supported for jobs with a docker image compute environment.
            artifacts_remote: The remote storage to persist your artifacts to.
                Should be of format <CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>.
                PATH_WITHIN_CONNECTION hereby is a path relative to the connection's root.
                E.g. efs:data:some-path would result in an EFS connection named `data` and to the path `some-path`
                within it.
                Note that the connection needs to be added to the teamspace already in order for it to be found.
                Only supported for jobs with a docker image compute environment.
        """
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
        """Submit a new multi-machine job to the Lightning AI platform.

        Args:
            num_machines: The number of machines to run on.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            cloud_account: The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                If not provided will fall back to the teamspaces default cloud account.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            artifacts_local: The path of inside the docker container, you want to persist images from.
                CAUTION: When setting this to "/", it will effectively erase your container.
                Only supported for jobs with a docker image compute environment.
            artifacts_remote: The remote storage to persist your artifacts to.
                Should be of format <CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>.
                PATH_WITHIN_CONNECTION hereby is a path relative to the connection's root.
                E.g. efs:data:some-path would result in an EFS connection named `data` and to the path `some-path`
                within it.
                Note that the connection needs to be added to the teamspace already in order for it to be found.
                Only supported for jobs with a docker image compute environment.
        """

    @property
    @abstractmethod
    def machines(self) -> Tuple[MMTMachine, ...]:
        """Returns the sub-jobs for each individual instance."""

    @property
    @abstractmethod
    def machine(self) -> "Machine":
        """Returns the machine type this job is running on."""

    @abstractmethod
    def stop(self) -> None:
        """Stops the job."""

    @abstractmethod
    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """

    @property
    @abstractmethod
    def status(self) -> "Status":
        """The current status of the job."""

    @property
    @abstractmethod
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem."""

    @property
    @abstractmethod
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem."""

    @property
    def share_path(self) -> Optional[str]:
        """Path to the jobs share path."""
        return None

    @property
    def name(self) -> str:
        """The job's name."""
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        """The teamspace the job is part of."""
        return self._teamspace

    @property
    def logs(self) -> str:
        """Logs of the rank 0 machine."""
        return self.machines[0].logs

    @abstractmethod
    def _update_internal_job(self) -> None:
        pass
