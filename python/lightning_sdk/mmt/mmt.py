import warnings
from typing import TYPE_CHECKING, Any, Dict, Optional, Protocol, Tuple, TypedDict, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.mmt_api import MMTApiV2
from lightning_sdk.api.utils import AccessibleResource, _get_cloud_url, raise_access_error_if_not_allowed
from lightning_sdk.status import Status
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import (
    _get_org_id,
    _resolve_default_cloud_account,
    _resolve_teamspace,
    _setup_logger,
    _warn_deprecated_cloud_selection,
    in_studio,
    skip_studio_setup,
)

if TYPE_CHECKING:
    from lightning_sdk.job import Job
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

_logger = _setup_logger(__name__)


class MachineDict(TypedDict):
    name: str
    status: Status
    machine: Union["Machine", str]


class MMTMachine(Protocol):
    """A single machine in multi-machine training."""

    @property
    def name(self) -> str:
        """The name of the individual machine. Usually corresponds to the rank.

        Returns:
            str: The name of this machine instance.
        """
        ...

    @property
    def machine(self) -> Union["Machine", str]:
        """The actual machine type this node is running on.

        Returns:
            Union[Machine, str]: The machine type of this node.
        """
        ...

    @property
    def artifact_path(self) -> Optional[str]:
        """The path to the artifacts of this job.

        Returns:
            Optional[str]: The artifact path, or None if not available.
        """
        ...

    @property
    def status(self) -> Status:
        """The status of this job.

        Returns:
            Status: The current status of this machine's job.
        """
        ...

    @property
    def logs(self) -> str:
        """The logs of the given machine.

        Returns:
            str: The complete logs from this machine's execution.
        """
        ...

    def dict(self) -> MachineDict:
        """Dict representation of the given machine.

        Returns:
            MachineDict: A dictionary containing the machine's name, status, and machine type.
        """
        ...


class MMT(metaclass=TrackCallsMeta):
    """Submit and manage multi-machine jobs on the Lightning AI Platform."""

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
    ) -> None:
        """Fetch already existing multi-machine jobs.

        Args:
            name: the name of the job.
            teamspace: the teamspace the job is part of.
            org: the name of the organization owning the ``teamspace`` in case it is owned by an org.
            user: the name of the user owning the ``teamspace`` in case it is owned directly by a user instead
                of an org.

        Raises:
            ValueError: If the teamspace cannot be resolved from the provided arguments, or if the job is not found
                when ``_fetch_job=True``.
            PermissionError: If the user does not have access to jobs in the given teamspace.
        """
        teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        if teamspace is None:
            raise ValueError(
                "Cannot resolve the teamspace from provided arguments."
                f" Got teamspace={teamspace}, org={org}, user={user}."
            )

        raise_access_error_if_not_allowed(AccessibleResource.Jobs, teamspace_id=teamspace.id)

        self._teamspace = teamspace
        self._name = name
        self._job = None
        self._prevent_refetch_latest = False
        self._cloud_account_api = CloudAccountApi()
        self._job_api = MMTApiV2()

        if _fetch_job:
            self._update_internal_job()

    @classmethod
    def run(
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
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: Optional[str] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        reuse_snapshot: bool = True,
    ) -> "MMT":
        """Run async workloads using a docker image across multiple machines.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            num_machines: The number of machines to run on.
            machine: The machine type to run the job on.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
            org: The organization owning the teamspace, if any. Defaults to the current organization.
            user: The user owning the teamspace, if any. Defaults to the current user.
            cloud: Cloud provider or cloud account to run the job on.
            cloud_account: Deprecated. Use ``cloud`` instead. The cloud account to run the job on. Defaults to the
                studio cloud account if running with studio compute env, otherwise falls back to the teamspace default.
            cloud_provider: Deprecated. Use ``cloud`` instead. The provider to select the cloud account from. If set,
                must agree with the provider of the cloud account, if specified.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. Cheaper but can be preempted.
            image_credentials: Credentials secret name used to pull a private image.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider, such as ECR.
            artifacts_local: The path inside the docker container to persist artifacts from.
                Only supported for jobs with a docker image compute environment.
            artifacts_remote: The remote storage to persist your artifacts to. Should be of format
                ``<CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>``.
            entrypoint: The entrypoint of your docker container. Defaults to ``sh -c`` which
                just runs the provided command in a standard shell if a command is provided.
                If no command is provided, it will run the pre-defined entrypoint of the provided image.
                To use the pre-defined entrypoint of the provided image with a specified command,
                set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: Maps container paths to data-connection paths in the form
                ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>:<PATH>"}`` or ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>"}``
                for the root of a connection. Only applicable when submitting docker jobs.
            max_runtime: Duration in seconds to allocate the machine. Required for some top-end GCP machines.
                Defaults to 3 hours.
            reuse_snapshot: Whether to reuse a Studio snapshot when multiple jobs for the same Studio are
                submitted. Turning this off may result in longer startup times. Defaults to True.

        Returns:
            MMT: The newly submitted multi-machine job instance.

        Raises:
            ValueError: If required arguments are missing or mutually exclusive arguments are both provided.
            RuntimeError: If image and studio are both provided.
        """
        from lightning_sdk.lightning_cloud.openapi.rest import ApiException
        from lightning_sdk.studio import Studio

        explicit_cloud_account = cloud_account
        explicit_cloud_provider = cloud_provider
        _warn_deprecated_cloud_selection(cloud_account=explicit_cloud_account, cloud_provider=explicit_cloud_provider)
        if cloud is not None and (explicit_cloud_account is not None or explicit_cloud_provider is not None):
            raise ValueError("Cannot use 'cloud' with 'cloud_account' or 'cloud_provider'.")
        cloud_account = _resolve_default_cloud_account(cloud_account)

        if num_machines <= 1:
            raise ValueError("Multi-Machine training cannot be run with less than 2 Machines")

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
                        cloud=cloud,
                        cloud_account=cloud_account,
                        create_ok=False,
                    )

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

            if entrypoint is not None:
                raise ValueError("Specifying the entrypoint has no effect for jobs with Studio envs.")

        else:
            if studio is not None:
                raise RuntimeError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )

            if cloud_account is None and cloud is None and in_studio():
                try:
                    with skip_studio_setup():
                        resolve_studio = Studio(teamspace=teamspace, user=user, org=org)
                    cloud_account = resolve_studio.cloud_account
                except (ValueError, ApiException):
                    warnings.warn("Could not infer cloud account from studio. Using teamspace default.")

            if bool(artifacts_local) != bool(artifacts_remote):
                raise ValueError("Artifact persistence requires both artifacts_local and artifacts_remote to be set")

            if artifacts_remote and len(artifacts_remote.split(":")) != 3:
                raise ValueError(
                    "Artifact persistence requires exactly three arguments separated by colon of kind "
                    f"<CONNECTION_TYPE>:<CONNECTION_NAME>:<PATH_WITHIN_CONNECTION>, got {artifacts_local}"
                )

            if command is not None and entrypoint is None:
                entrypoint = "sh -c"
            elif entrypoint == "" or entrypoint is None:
                entrypoint = None

        mmt = cls(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=False)
        submit_cloud = cloud if cloud_account is None else None
        mmt._submit(
            num_machines=num_machines,
            machine=machine,
            cloud=submit_cloud,
            command=command,
            studio=studio,
            image=image,
            env=env,
            interruptible=interruptible,
            cloud_account=cloud_account,
            cloud_provider=cloud_provider,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
        )

        _logger.info(f"Multi-Machine Job was successfully launched. View it at {mmt.link}")
        return mmt

    def _submit(
        self,
        num_machines: int,
        machine: Union["Machine", str],
        cloud: Optional[Union["CloudProvider", str]] = None,
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union["CloudProvider", str]] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: Optional[str] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        artifacts_local: Optional[str] = None,
        artifacts_remote: Optional[str] = None,
        reuse_snapshot: bool = True,
    ) -> "MMT":
        if studio is not None:
            studio_id = studio._studio.id
            if image is not None:
                raise ValueError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )
            if command is None:
                raise ValueError("command is required when using a studio")
        else:
            studio_id = None
            if image is None:
                raise ValueError("either image or studio must be provided")

        cloud_account = self._cloud_account_api.resolve_cloud_account(
            self._teamspace.id,
            cloud=cloud,
            cloud_account=cloud_account,
            cloud_provider=cloud_provider,
            default_cloud_account=self._teamspace.default_cloud_account,
        )

        submitted = self._job_api.submit_job(
            name=self.name,
            num_machines=num_machines,
            command=command,
            cloud_account=cloud_account,
            teamspace_id=self._teamspace.id,
            studio_id=studio_id,
            image=image,
            machine=machine,
            interruptible=interruptible,
            env=env,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
        )
        self._job = submitted
        self._name = submitted.name
        return self

    @property
    def machines(self) -> Tuple["Job", ...]:
        from lightning_sdk.job import Job

        return tuple(
            Job(name=j.name, teamspace=self.teamspace)
            for j in self._job_api.list_mmt_subjobs(self._guaranteed_job.id, self.teamspace.id)
        )

    def stop(self) -> None:
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return
        self._job_api.stop_job(job_id=self._guaranteed_job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        self._job_api.delete_job(
            job_id=self._guaranteed_job.id,
            teamspace_id=self._teamspace.id,
        )

    def wait(self, interval: float = 5.0, timeout: Optional[float] = None, stop_on_timeout: bool = False) -> None:
        import time

        start = time.time()
        while True:
            if self.status in (Status.Completed, Status.Stopped, Status.Failed):
                break

            if timeout is not None and time.time() - start > timeout:
                if stop_on_timeout:
                    self.stop()
                raise TimeoutError("Job didn't finish within the provided timeout.")

            time.sleep(interval)

    async def async_wait(
        self, interval: float = 5.0, timeout: Optional[float] = None, stop_on_timeout: bool = False
    ) -> None:
        import asyncio

        start = asyncio.get_event_loop().time()
        while True:
            if self.status in (Status.Completed, Status.Stopped, Status.Failed):
                break

            if timeout is not None and asyncio.get_event_loop().time() - start > timeout:
                if stop_on_timeout:
                    self.stop()
                raise TimeoutError("Job didn't finish within the provided timeout.")

            await asyncio.sleep(interval)

    @property
    def status(self) -> Status:
        return self._job_api._job_state_to_external(self._latest_job.state)

    @property
    def artifact_path(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def snapshot_path(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def share_path(self) -> Optional[str]:
        return None

    @property
    def machine(self) -> Union["Machine", str]:
        return self._job_api._get_job_machine_from_spec(
            self._guaranteed_job.spec,
            self.teamspace.id,
            _get_org_id(self.teamspace),
        )

    def _update_internal_job(self) -> None:
        if getattr(self, "_job", None) is None:
            self._job = self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id)
            return

        self._job = self._job_api.get_job(job_id=self._job.id, teamspace_id=self._teamspace.id)

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace

    @property
    def link(self) -> str:
        return f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/jobs/{self.name}?app_id=mmt"

    @property
    def image(self) -> Optional[str]:
        return self._job_api.get_image_name(self._guaranteed_job)

    @property
    def studio(self) -> Optional["Studio"]:
        from lightning_sdk.studio import Studio

        studio_name = self._job_api.get_studio_name(self._guaranteed_job)
        if not studio_name:
            return None
        return Studio(studio_name, teamspace=self.teamspace)

    @property
    def command(self) -> str:
        return self._job_api.get_command(self._guaranteed_job)

    @property
    def num_machines(self) -> int:
        return self._job_api.get_num_machines(self._guaranteed_job)

    @property
    def logs(self) -> str:
        raise NotImplementedError

    def dict(self) -> Dict[str, object]:
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
        import json

        return json.dumps(self.dict(), indent=4, sort_keys=True, default=str)

    @property
    def _guaranteed_job(self) -> Any:
        if getattr(self, "_job", None) is None:
            self._update_internal_job()

        return self._job

    @property
    def total_cost(self) -> float:
        return self._job_api.get_total_cost(self._latest_job)

    @property
    def _latest_job(self) -> Any:
        if self._prevent_refetch_latest:
            return self._guaranteed_job

        self._update_internal_job()
        return self._job
