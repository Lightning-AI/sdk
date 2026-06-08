from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.utils import AccessibleResource, raise_access_error_if_not_allowed
from lightning_sdk.mmt.base import MMTMachine, _BaseMMT
from lightning_sdk.mmt.v1 import _MMTV1
from lightning_sdk.mmt.v2 import _MMTV2
from lightning_sdk.utils.resolve import _resolve_teamspace, _setup_logger

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.status import Status
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

_logger = _setup_logger(__name__)


class MMT(_BaseMMT):
    """Class to submit and manage multi-machine jobs on the Lightning AI Platform."""

    _force_v1: bool = (
        False  # required for studio plugin still working correctly as v2 currently does not support the studio env
    )

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

        Raises:
            ValueError: If the job is not found in the given teamspace.
            PermissionError: If the user does not have access to jobs in the given teamspace.
        """
        teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        raise_access_error_if_not_allowed(AccessibleResource.Jobs, teamspace_id=teamspace.id)

        from lightning_sdk.lightning_cloud.openapi.rest import ApiException

        if not self._force_v1:
            # try with v2 and fall back to v1
            try:
                mmt = _MMTV2(
                    name=name,
                    teamspace=teamspace,
                    org=org,
                    user=user,
                    _fetch_job=_fetch_job,
                )
            except ApiException as e:
                try:
                    mmt = _MMTV1(
                        name=name,
                        teamspace=teamspace,
                        org=org,
                        user=user,
                        _fetch_job=_fetch_job,
                    )
                except ApiException:
                    raise e from e

        else:
            mmt = _MMTV1(
                name=name,
                teamspace=teamspace,
                org=org,
                user=user,
                _fetch_job=_fetch_job,
            )

        self._internal_mmt = mmt
        self._cloud_account_api = CloudAccountApi()

    @classmethod
    def run(
        cls,
        name: str,
        num_machines: int,
        machine: Union["Machine", str],
        cloud: Optional[Union["CloudProvider", str]] = None,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Union[str, None] = None,
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
            machine: The machine type to run the job on.
            num_machines: The number of machines to run on.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
            org: The organization owning the teamspace (if any). Defaults to the current organization.
            user: The user owning the teamspace (if any). Defaults to the current user.
            cloud: Cloud provider or cloud account to run the job on.
            cloud_account: Deprecated. Use ``cloud`` instead. The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                Falls back to the teamspace default cloud account.
            cloud_provider: Deprecated. Use ``cloud`` instead. The provider to select the cloud-account from.
                If set, must be in agreement with the provider from the cloud_account (if specified).
                If not specified, falls back to the teamspace default cloud account.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            entrypoint: The entrypoint of your docker container. Defaults to `sh -c` which
                just runs the provided command in a standard shell if a command is provided.
                If no command is provided, it will run the pre-defined entrypoint of the provided image.
                To use the pre-defined entrypoint of the provided image with a specified command,
                set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: Maps container paths to data-connection paths in the form
                ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>:<PATH>"}`` or ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>"}``
                for the root of a connection. Only applicable when submitting docker jobs.
            reuse_snapshot: Whether the job should reuse a Studio snapshot when multiple jobs for the same Studio are
                submitted. Turning this off may result in longer job startup times. Defaults to True.

        Returns:
            MMT: The newly submitted multi-machine job instance.

        Raises:
            ValueError: If required arguments are missing or mutually exclusive arguments are both provided.
            RuntimeError: If both image and studio are provided.
        """
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
            cloud_provider=cloud_provider,
            env=env,
            interruptible=interruptible,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
            cloud=cloud,
        )
        # required for typing with "MMT"
        assert isinstance(ret_val, cls)

        msg = f"Multi-Machine Job was successfully launched. View it at {ret_val.link}"

        _logger.info(msg)
        return ret_val

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
        artifacts_local: Optional[str] = None,  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str] = None,  # deprecated in favor of path_mappings
        reuse_snapshot: bool = True,
    ) -> "MMT":
        """Submit a new multi-machine job to the Lightning AI platform.

        Args:
            num_machines: The number of machines to run on.
            machine: The machine type to run the job on.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
            image: The docker image to run the job with. Mutually exclusive with studio.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
            cloud: Cloud provider or cloud account to run the job on.
            cloud_account: Deprecated. Use ``cloud`` instead. The cloud account to run the job on.
                Defaults to the studio cloud account if running with studio compute env.
                Falls back to the teamspace default cloud account.
            cloud_provider: Deprecated. Use ``cloud`` instead. The provider to select the cloud-account from.
                If set, must be in agreement with the provider from the cloud_account (if specified).
                If not specified, falls back to the teamspace default cloud account.
            image_credentials: The credentials used to pull the image. Required if the image is private.
                This should be the name of the respective credentials secret created on the Lightning AI platform.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider (e.g. ECR).
            entrypoint: The entrypoint of your docker container. Defaults to `sh -c` which
                just runs the provided command in a standard shell if a command is provided.
                If no command is provided, it will run the pre-defined entrypoint of the provided image.
                To use the pre-defined entrypoint of the provided image with a specified command,
                set this to an empty string.
                Only applicable when submitting docker jobs.
            path_mappings: Maps container paths to data-connection paths in the form
                ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>:<PATH>"}`` or ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>"}``
                for the root of a connection. Only applicable when submitting docker jobs.
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h
            reuse_snapshot: Whether the job should reuse a Studio snapshot when multiple jobs for the same Studio are
                submitted. Turning this off may result in longer job startup times. Defaults to True.

        Returns:
            MMT: This MMT instance, updated with the submitted job state.
        """
        self._job = self._internal_mmt._submit(
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
            reuse_snapshot=reuse_snapshot,
            cloud=cloud,
        )
        return self

    def stop(self) -> None:
        """Stops the job."""
        return self._internal_mmt.stop()

    def delete(self) -> None:
        """Deletes the job.

        Caution: This also deletes all artifacts and snapshots associated with the job.
        """
        return self._internal_mmt.delete()

    @property
    def status(self) -> "Status":
        """The current status of the job (accumulated over all machines).

        Returns:
            Status: The current accumulated status across all machines.
        """
        return self._internal_mmt.status

    @property
    def machines(self) -> Tuple[MMTMachine, ...]:
        """Returns the sub-jobs for each individual instance.

        Returns:
            Tuple[MMTMachine, ...]: A tuple of MMTMachine instances, one per machine.
        """
        return self._internal_mmt.machines

    @property
    def machine(self) -> Union["Machine", str]:
        """Returns the machine type this job is running on.

        Returns:
            Union[Machine, str]: The machine type used by this multi-machine job.
        """
        return self._internal_mmt.machine

    @property
    def artifact_path(self) -> Optional[str]:
        """Path to the artifacts created by the job within the distributed teamspace filesystem.

        Returns:
            Optional[str]: The artifact path, or None if not available.
        """
        return self._internal_mmt.artifact_path

    @property
    def snapshot_path(self) -> Optional[str]:
        """Path to the studio snapshot used to create the job within the distributed teamspace filesystem.

        Returns:
            Optional[str]: The snapshot path, or None if not available.
        """
        return self._internal_mmt.snapshot_path

    @property
    def share_path(self) -> Optional[str]:
        """Path to the jobs share path.

        Returns:
            Optional[str]: Always None for multi-machine jobs.
        """
        return None

    def _update_internal_job(self) -> None:
        return self._internal_mmt._update_internal_job()

    @property
    def name(self) -> str:
        """The job's name.

        Returns:
            str: The job's name.
        """
        return self._internal_mmt.name

    @property
    def teamspace(self) -> "Teamspace":
        """The teamspace the job is part of.

        Returns:
            Teamspace: The teamspace this job belongs to.
        """
        return self._internal_mmt._teamspace

    @property
    def link(self) -> str:
        """The Lightning AI web URL to view this multi-machine job.

        Returns:
            str: Direct URL to the job's page on lightning.ai.
        """
        return self._internal_mmt.link

    @property
    def studio(self) -> Optional["Studio"]:
        """The studio used to submit the MMT.

        Returns:
            Optional[Studio]: The Studio instance used to submit this job, or None if an image was used.
        """
        return self._internal_mmt.studio

    @property
    def image(self) -> Optional[str]:
        """The image used to submit the MMT.

        Returns:
            Optional[str]: The docker image name, or None if a studio was used.
        """
        return self._internal_mmt.image

    @property
    def command(self) -> str:
        """The command the MMT is running.

        Returns:
            str: The command being executed by this job.
        """
        return self._internal_mmt.command

    def __getattr__(self, key: str) -> Any:
        """Forward the attribute lookup to the internal job implementation.

        Args:
            key: The attribute name to look up.

        Returns:
            Any: The attribute value from the internal MMT implementation.
        """
        try:
            return getattr(super(), key)
        except AttributeError:
            return getattr(self._internal_mmt, key)

    @property
    def _guaranteed_job(self) -> Any:
        return self._internal_mmt._guaranteed_job
