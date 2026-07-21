import warnings
from pathlib import PurePath
from typing import TYPE_CHECKING, Any, Dict, Optional, TypedDict, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.utils import AccessibleResource, _get_cloud_url, raise_access_error_if_not_allowed
from lightning_sdk.status import Status
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import (
    _get_org_id,
    _resolve_default_cloud_account,
    _resolve_teamspace,
    _setup_logger,
    in_studio,
    skip_studio_setup,
)

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

_logger = _setup_logger(__name__)

__all__ = [
    "Job",
]


class JobDict(TypedDict):
    name: str
    command: str
    teamspace: str
    studio: Optional[str]
    image: Optional[str]
    status: Status
    machine: Union["Machine", str]
    total_cost: float


class Job(metaclass=TrackCallsMeta):
    """Submit and manage single-machine jobs on the Lightning AI Platform."""

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

        raise_access_error_if_not_allowed(AccessibleResource.Jobs, teamspace.id)

        self._teamspace = teamspace
        self._name = name
        self._job = None
        self._prevent_refetch_latest = False
        self._cloud_account_api = CloudAccountApi()
        self._job_api = JobApiV2()

        if _fetch_job:
            from lightning_sdk.lightning_cloud.openapi.rest import ApiException

            try:
                self._update_internal_job()
            except ApiException as ex:
                if ex.status == 404:
                    raise ValueError(f"Job {name} does not exist in Teamspace {teamspace.name}") from None
                raise

    @classmethod
    def run(
        cls,
        name: str,
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
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
    ) -> "Job":
        """Run async workloads using a docker image or a compute environment from your studio.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            machine: The machine type to run the job on.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
            org: The organization owning the teamspace, if any. Defaults to the current organization.
            user: The user owning the teamspace, if any. Defaults to the current user.
            cloud: Cloud provider or cloud account to run the job on.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. Cheaper but can be preempted.
            image_credentials: Credentials secret name used to pull a private image.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider, such as ECR.
            entrypoint: The entrypoint of your docker container. Defaults to ``sh -c``.
                Set to an empty string to use the image's pre-defined entrypoint with a command.
                Only applicable when submitting docker jobs.
            path_mappings: Maps container paths to data-connection paths in the form
                ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>:<PATH>"}`` or ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>"}``
                for the root of a connection. Only applicable when submitting docker jobs.
            max_runtime: Duration in seconds to allocate the machine. Required for some top-end GCP machines.
                Defaults to 3 hours.
            reuse_snapshot: Whether to reuse a Studio snapshot when multiple jobs for the same Studio are
                submitted. Turning this off may result in longer startup times. Defaults to True.
            scratch_disks: Optional mapping of scratch-disk mount paths to their sizes in GiB.
            placement_group_id: Optional placement group identifier for colocating the job.

        Returns:
            Job: The newly submitted Job instance.

        Raises:
            ValueError: If required arguments are missing or mutually exclusive arguments are both provided.
            RuntimeError: If image and studio are both provided.
        """
        from lightning_sdk.lightning_cloud.openapi.rest import ApiException
        from lightning_sdk.studio import Studio

        cloud_account = _resolve_default_cloud_account(None)
        if cloud is not None:
            cloud_account = None

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
                    "Studio cloud account does not match provided cloud account. "
                    "Can only run jobs with Studio envs in the same cloud account."
                )

            if image_credentials is not None:
                raise ValueError("image_credentials is only supported when using a custom image")

            if cloud_account_auth:
                raise ValueError("cloud_account_auth is only supported when using a custom image")

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

            if command is not None and entrypoint is None:
                entrypoint = "sh -c"
            elif entrypoint == "" or entrypoint is None:
                entrypoint = None

        job = cls(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=False)
        submit_cloud = cloud if cloud_account is None else None

        job._submit(
            machine=machine,
            cloud=submit_cloud,
            command=command,
            studio=studio,
            image=image,
            env=env,
            interruptible=interruptible,
            cloud_account=cloud_account,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
            scratch_disks=scratch_disks,
            placement_group_id=placement_group_id,
        )

        _logger.info(f"Job was successfully launched. View it at {job.link}")
        return job

    def _submit(
        self,
        machine: Union["Machine", str],
        cloud: Optional[Union["CloudProvider", str]] = None,
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: Optional[str] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        reuse_snapshot: bool = True,
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
    ) -> "Job":
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
            cloud=cloud or cloud_account,
            default_cloud_account=self._teamspace.default_cloud_account,
        )

        if scratch_disks:
            if studio is None:
                raise ValueError("scratch_disks are only supported within a studio job")

            if len(scratch_disks) > 5:
                raise ValueError("scratch_disk may only contain up to 5 elements")

            for raw_path, size in scratch_disks.items():
                if size > 50000:
                    raise ValueError("scratch_disk size cannot exceed 50TiB")

                path = PurePath(raw_path)
                if path.is_absolute():
                    try:
                        path.relative_to("/teamspace/scratch")
                    except ValueError:
                        raise ValueError("scratch_disk paths must be relative to /teamspace/scratch") from None

                if ".." in path.parts:
                    raise ValueError("scratch_disk path cannot contain '..'")

        submitted = self._job_api.submit_job(
            name=self.name,
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
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
            scratch_disks=scratch_disks,
            placement_group_id=placement_group_id,
        )
        self._job = submitted
        self._name = submitted.name
        return self

    def stop(self) -> None:
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return

        self._job_api.stop_job(job_id=self._guaranteed_job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        self._job_api.delete_job(
            job_id=self._guaranteed_job.id,
            teamspace_id=self._teamspace.id,
            cloudspace_id=self._guaranteed_job.spec.cloudspace_id,
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
        try:
            return self._job_api._job_state_to_external(self._latest_job.state)
        except Exception:
            raise RuntimeError(
                f"Job {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    @property
    def machine(self) -> Union["Machine", str]:
        return self._job_api._get_job_machine_from_spec(
            self._guaranteed_job.spec,
            self.teamspace.id,
            _get_org_id(self.teamspace),
        )

    @property
    def public_ip(self) -> Optional[str]:
        try:
            return self._job.public_ip_address
        except AttributeError:
            return None

    @property
    def resource_id(self) -> Optional[str]:
        return self._guaranteed_job.id

    @property
    def private_ip_address(self) -> Optional[str]:
        return self._guaranteed_job.private_ip_address

    @property
    def placement_group_id(self) -> Optional[str]:
        return self._guaranteed_job.spec.placement_group_id

    @property
    def rank(self) -> Optional[int]:
        return self._guaranteed_job.spec.rank

    @property
    def artifact_path(self) -> Optional[str]:
        if self._guaranteed_job.spec.image != "":
            if self._guaranteed_job.spec.artifacts_destination:
                (
                    connection_type,
                    connection_name,
                    connection_path,
                ) = self._guaranteed_job.spec.artifacts_destination.split(":")
                return f"/teamspace/{connection_type}_connections/{connection_name}/{connection_path}"
            return None

        return f"/teamspace/jobs/{self._guaranteed_job.name}/artifacts"

    @property
    def snapshot_path(self) -> Optional[str]:
        if self._guaranteed_job.spec.image != "":
            return None
        return f"/teamspace/jobs/{self._guaranteed_job.name}/snapshot"

    @property
    def share_path(self) -> Optional[str]:
        raise NotImplementedError("Not implemented yet")

    @property
    def logs(self) -> str:
        if self.status not in (Status.Failed, Status.Completed, Status.Stopped):
            raise RuntimeError("Getting jobs logs while the job is pending or running is not supported yet!")

        return self._job_api.get_logs_finished(job_id=self._guaranteed_job.id, teamspace_id=self.teamspace.id)

    @property
    def link(self) -> str:
        mmt_name = self._job_api.get_mmt_name(self._guaranteed_job)

        if self._job_api.get_image_name(self._guaranteed_job):
            if mmt_name:
                return (
                    f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/"
                    f"jobs/{mmt_name}?app_id=mmt&machine_name={self.name}"
                )
            return f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/jobs/{self.name}?app_id=jobs"

        studio_name = self._job_api.get_studio_name(self._guaranteed_job)
        if not studio_name:
            raise RuntimeError("Cannot extract studio name from job")
        return (
            f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/studios/"
            f"{studio_name}/app?app_id=jobs&job_name={self.name}"
        )

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

    def dict(self) -> JobDict:
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
