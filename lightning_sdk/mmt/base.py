import warnings
from abc import abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, Tuple, Union

if TYPE_CHECKING:
    from lightning_sdk.job.base import MachineDict
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

from lightning_sdk.job.base import _BaseJob
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster, in_studio


class MMTMachine(Protocol):
    """A single machine in multi-machine training."""

    @property
    def name(self) -> str:
        """The Name of the individual machine. Usually corresponds to the rank."""
        ...

    @property
    def machine(self) -> Union["Machine", str]:
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

    def dict(self) -> "MachineDict":
        """Dict representation of the given machine."""
        ...


class _BaseMMT(_BaseJob):
    """Base interface to all job types."""

    @classmethod
    def run(
        cls,
        name: str,
        machine: Union["Machine", str],
        num_machines: int,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Optional[str] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        artifacts_local: Optional[str] = None,  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str] = None,  # deprecated in favor of path_mappings
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
                If not provided and `cloud_account_provider` is set, will resolve cluster from this, else
                will fall back to the teamspaces default cloud account.
            cloud_account_provider: The provider to select the cloud-account from.
                If set, must be in agreement with the provider from the cloud_account (if specified).
                If not specified, falls backto the teamspace default cloud account.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            entrypoint: The entrypoint of your docker container. Defaults to `sh -c` which
                just runs the provided command in a standard shell.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: Dictionary of path mappings. The keys are the path inside the container whereas the value
                represents the data-connection name and the path inside that connection.
                Should be of form
                    {
                        "<CONTAINER_PATH_1>": "<CONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1>",
                        "<CONTAINER_PATH_2>": "<CONNECTION_NAME_2>"
                    }
                If the path inside the connection is omitted it's assumed to be the root path of that connection.
                Only applicable when submitting docker jobs.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
        """
        from lightning_sdk.lightning_cloud.openapi.rest import ApiException
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

            if entrypoint != "sh -c":
                raise ValueError("Specifying the entrypoint has no effect for jobs with Studio envs.")

        else:
            if studio is not None:
                raise RuntimeError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )

            if cloud_account is None and in_studio():
                try:
                    resolve_studio = Studio(teamspace=teamspace, user=user, org=org)
                    cloud_account = resolve_studio.cloud_account
                except (ValueError, ApiException):
                    warnings.warn("Could not infer cloud account from studio. Using teamspace default.")

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
            cloud_provider=cloud_provider,
            command=command,
            studio=studio,
            image=image,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            max_runtime=max_runtime,
        )
        return inst

    @abstractmethod
    def _submit(
        self,
        num_machines: int,
        machine: Union["Machine", str],
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        artifacts_local: Optional[str] = None,  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str] = None,  # deprecated in favor of path_mappings
        max_runtime: Optional[int] = None,
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
            entrypoint: The entrypoint of your docker container. Defaults to sh -c.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: Dictionary of path mappings. The keys are the path inside the container whereas the value
                represents the data-connection name and the path inside that connection.
                Should be of form
                    {
                        "<CONTAINER_PATH_1>": "<CONNECTION_NAME_1>:<PATH_WITHIN_CONNECTION_1>",
                        "<CONTAINER_PATH_2>": "<CONNECTION_NAME_2>"
                    }
                If the path inside the connection is omitted it's assumed to be the root path of that connection.
                Only applicable when submitting docker jobs.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
        """

    @property
    @abstractmethod
    def machines(self) -> Tuple[MMTMachine, ...]:
        """Returns the sub-jobs for each individual instance."""

    @property
    def num_machines(self) -> int:
        """Returns the number of machines assigned to this multi-machine job."""
        return len(self.machines)

    @property
    @abstractmethod
    def machine(self) -> Union["Machine", str]:
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

    def dict(
        self
    ) -> Dict[
        str,
        Union[
            str,
            float,
            "Studio",
            "Status",
            "Machine",
            None,
            List[Dict[str, Union[str, "Status", "Machine"]]],
        ],
    ]:
        """Dict representation of this job."""
        studio = self.studio

        return {
            "name": self.name,
            "teamspace": f"{self.teamspace.owner.name}/{self.teamspace.name}",
            "studio": studio.name if studio else None,
            "image": self.image,
            "command": self.command,
            "status": self.status,
            "machine": self.machine,
            "machines": [
                {"name": d["name"], "status": d["status"], "machine": d["machine"]}
                for d in (x.dict() for x in self.machines)
            ],
            "total_cost": self.total_cost,
        }

    @abstractmethod
    def _update_internal_job(self) -> None:
        pass
