import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, TypedDict, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.utils import _get_cloud_url
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster, _resolve_teamspace, in_studio, skip_studio_setup

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User


class MachineDict(TypedDict):
    name: str
    status: "Status"
    machine: Union["Machine", str]


class JobDict(MachineDict):
    command: str
    teamspace: str
    studio: Optional[str]
    image: Optional[str]
    total_cost: float


class _BaseJob(ABC):
    """Base interface to all job types."""

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        """Fetch already existing jobs.

        Args:
            name: the name of the job
            teamspace: the teamspace the job is part of
            org: the name of the organization owning the :param`teamspace` in case it is owned by an org
            user: the name of the user owning the :param`teamspace`
                in case it is owned directly by a user instead of an org.
        """
        _teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        if _teamspace is None:
            raise ValueError(
                "Cannot resolve the teamspace from provided arguments."
                f" Got teamspace={teamspace}, org={org}, user={user}."
            )
        else:
            self._teamspace = _teamspace
        self._name = name
        self._job = None

        if _fetch_job:
            self._update_internal_job()

        self._prevent_refetch_latest = False
        self._cloud_account_api = CloudAccountApi()

    @classmethod
    def run(
        cls,
        name: str,
        machine: Union["Machine", str],
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
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> "_BaseJob":
        """Run async workloads using a docker image or a compute environment from your studio.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
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
            entrypoint: The entrypoint of your docker container. Defaults to `sh -c` which
                just runs the provided command in a standard shell.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
        """
        from lightning_sdk.lightning_cloud.openapi.rest import ApiException
        from lightning_sdk.studio import Studio

        cloud_account = _resolve_deprecated_cluster(cloud_account, cluster)

        if not name:
            raise ValueError("A job needs to have a name!")

        if image is None:
            if not isinstance(studio, Studio):
                with skip_studio_setup():
                    studio = Studio(
                        name=studio,
                        teamspace=teamspace,
                        org=org,
                        user=user,
                        cloud_account=cloud_account,
                        create_ok=False,
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
                    "Studio cloud account does not match provided cloud account. "
                    "Can only run jobs with Studio envs in the same cloud account."
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
                    with skip_studio_setup():
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
        return inst._submit(
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
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            max_runtime=max_runtime,
        )

    @abstractmethod
    def _submit(
        self,
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
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        entrypoint: str = "sh -c",
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
    ) -> "_BaseJob":
        """Submit a new job to the Lightning AI platform.

        Args:
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            cloud_account: The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                If not provided and `cloud_account_provider` is set, will resolve cluster from this, else
                will fall back to the teamspaces default cloud account.
            cloud_account_provider: The provider to select the cloud-account from.
                If set, must be in agreement with the provider from the cloud_account (if specified).
                If not specified, falls backto the teamspace default cloud account.
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
            entrypoint: The entrypoint of your docker container. Defaults to sh -c.
                To use the pre-defined entrypoint of the provided image, set this to an empty string.
                Only applicable when submitting docker jobs.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
        """

    @abstractmethod
    def stop(self) -> None:
        """Stops the job.

        This is blocking until the job is stopped.
        """

    @abstractmethod
    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """

    def wait(self, interval: float = 5.0, timeout: Optional[float] = None, stop_on_timeout: bool = False) -> None:
        """Waits for the job to be either completed, manually stopped or failed.

        Args:
            interval: The number of seconds to spend in-between status checks.
            timeout: The maximum number of seconds to wait before raising an error. If None, waits forever.
            stop_on_timeout: Whether to stop the job if it didn't finish within the timeout.
        """
        import time

        from lightning_sdk.status import Status

        start = time.time()
        while True:
            if self.status in (Status.Completed, Status.Stopped, Status.Failed):
                break

            if timeout is not None and time.time() - start > timeout:
                if stop_on_timeout:
                    self.stop()  # ensure the job is stopped if it didn't finish
                raise TimeoutError("Job didn't finish within the provided timeout.")

            time.sleep(interval)

    async def async_wait(
        self, interval: float = 5.0, timeout: Optional[float] = None, stop_on_timeout: bool = False
    ) -> None:
        """Waits for the job to be either completed, manually stopped or failed.

        Args:
            interval: The number of seconds to spend in-between status checks.
            timeout: The maximum number of seconds to wait before raising an error. If None, waits forever.
            stop_on_timeout: Whether to stop the job if it didn't finish within the timeout.
        """
        import asyncio

        from lightning_sdk.status import Status

        start = asyncio.get_event_loop().time()
        while True:
            if self.status in (Status.Completed, Status.Stopped, Status.Failed):
                break

            if timeout is not None and asyncio.get_event_loop().time() - start > timeout:
                if stop_on_timeout:
                    self.stop()  # ensure the job is stopped if it didn't finish
                raise TimeoutError("Job didn't finish within the provided timeout.")

            await asyncio.sleep(interval)

    @property
    @abstractmethod
    def status(self) -> "Status":
        """The current status of the job."""

    @property
    @abstractmethod
    def machine(self) -> Union["Machine", str]:
        """The machine type the job is running on."""

    @property
    @abstractmethod
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem."""

    @property
    @abstractmethod
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem."""

    @property
    @abstractmethod
    def share_path(self) -> Optional[str]:
        """Path to the jobs share path."""

    @abstractmethod
    def _update_internal_job(self) -> None:
        pass

    @property
    def name(self) -> str:
        """The job's name."""
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        """The teamspace the job is part of."""
        return self._teamspace

    @property
    @abstractmethod
    def logs(self) -> str:
        """The logs of the job."""

    @property
    @abstractmethod
    def image(self) -> Optional[str]:
        """The image used to submit the job."""

    @property
    @abstractmethod
    def studio(self) -> Optional["Studio"]:
        """The studio used to submit the job."""

    @property
    @abstractmethod
    def command(self) -> str:
        """The command the job is running."""

    def dict(self) -> JobDict:
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
            "total_cost": self.total_cost,
        }

    def json(self) -> str:
        """JSON representation of this job."""
        import json

        return json.dumps(self.dict(), indent=4, sort_keys=True, default=str)

    @property
    def link(self) -> str:
        """A link to view the current job in the UI."""
        studio_name = self._job_api.get_studio_name(self._guaranteed_job)
        if not studio_name:
            raise RuntimeError("Cannot extract studio name from job")
        return (
            f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/studios/"
            f"{studio_name}/app?app_id=jobs&job_name={self.name}"
        )

    @property
    def _guaranteed_job(self) -> Any:
        """Guarantees that the job was fetched at some point before returning it.

        Doesn't guarantee to have the lastest version of the job. Use _latest_job for that.
        """
        if getattr(self, "_job", None) is None:
            self._update_internal_job()

        return self._job

    @property
    def total_cost(self) -> float:
        """The number of credits the job was consuming so far."""
        return self._job_api.get_total_cost(self._latest_job)

    @property
    def _latest_job(self) -> Any:
        """Guarantees to fetch the latest version of a job before returning it."""
        # in some cases we know we just refetched the latest state, no need to refetch again
        if self._prevent_refetch_latest:
            return self._guaranteed_job

        self._update_internal_job()
        return self._job
