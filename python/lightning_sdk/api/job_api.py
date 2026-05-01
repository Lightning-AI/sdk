import time
from typing import TYPE_CHECKING, Dict, List, Optional, Union
from urllib.request import urlopen

from lightning_sdk.api.utils import (
    _create_app,
    _machine_to_compute_name,
    remove_datetime_prefix,
    resolve_path_mappings,
)
from lightning_sdk.api.utils import _get_cloud_url as _cloud_url
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    Externalv1Lightningwork,
    JobsServiceCreateJobBody,
    JobsServiceUpdateJobBody,
    LightningappInstanceServiceUpdateLightningappInstanceBody,
    V1CloudSpace,
    V1ClusterAccelerator,
    V1DownloadJobLogsResponse,
    V1DownloadLightningappInstanceLogsResponse,
    V1EnvVar,
    V1Job,
    V1JobSpec,
    V1LightningappInstanceSpec,
    V1LightningappInstanceState,
    V1LightningappInstanceStatus,
    V1LightningworkSpec,
    V1LightningworkState,
    V1ListLightningworkResponse,
    V1UserRequestedComputeConfig,
    V1Volume,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

if TYPE_CHECKING:
    from lightning_sdk.status import Status


class JobApiV1:
    """Legacy (v1 app-based) API client for single-machine Jobs."""

    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)

    def get_job(self, job_name: str, teamspace_id: str) -> Externalv1LightningappInstance:
        """Fetch a v1 job by name, raising ``ValueError`` if it does not exist.

        Args:
            job_name: The name of the job to look up.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``Externalv1LightningappInstance`` object.

        Raises:
            ValueError: If no job with the given name exists in the teamspace.
        """
        try:
            return self._client.lightningapp_instance_service_find_lightningapp_instance(
                project_id=teamspace_id, name=job_name
            )

        except Exception:
            raise ValueError(f"Job {job_name} does not exist") from None

    def get_job_status(self, job_id: str, teamspace_id: str) -> V1LightningappInstanceState:
        """Return the current phase of a v1 job instance, or ``None`` if status is unavailable.

        Args:
            job_id: The unique identifier of the job instance.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The current ``V1LightningappInstanceState`` phase, or ``None`` if the status object is absent.
        """
        instance = self._client.lightningapp_instance_service_get_lightningapp_instance(
            project_id=teamspace_id, id=job_id
        )

        status: V1LightningappInstanceStatus = instance.status

        if status is not None:
            return status.phase
        return None

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
        """Request to stop a v1 job and wait until it reaches a terminal state.

        Args:
            job_id: The unique identifier of the job instance to stop.
            teamspace_id: The ID of the teamspace that owns the job.
        """
        body = LightningappInstanceServiceUpdateLightningappInstanceBody(
            spec=V1LightningappInstanceSpec(desired_state=V1LightningappInstanceState.STOPPED)
        )
        self._client.lightningapp_instance_service_update_lightningapp_instance(
            project_id=teamspace_id,
            id=job_id,
            body=body,
        )

        # wait for job to be stopped
        while True:
            status = self.get_job_status(job_id, teamspace_id)
            if status in (
                V1LightningappInstanceState.STOPPED,
                V1LightningappInstanceState.FAILED,
                V1LightningappInstanceState.COMPLETED,
            ):
                break
            time.sleep(1)

    def delete_job(self, job_id: str, teamspace_id: str) -> None:
        """Permanently delete a v1 job instance.

        Args:
            job_id: The unique identifier of the job instance to delete.
            teamspace_id: The ID of the teamspace that owns the job.
        """
        self._client.lightningapp_instance_service_delete_lightningapp_instance(project_id=teamspace_id, id=job_id)

    def list_works(self, job_id: str, teamspace_id: str) -> List[Externalv1Lightningwork]:
        """Return the Lightning work units (sub-tasks) associated with a v1 job.

        Args:
            job_id: The unique identifier of the parent job instance.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            A list of ``Externalv1Lightningwork`` objects belonging to the job.
        """
        resp: V1ListLightningworkResponse = self._client.lightningwork_service_list_lightningwork(
            project_id=teamspace_id, app_id=job_id
        )
        return resp.lightningworks

    def get_work(self, job_id: str, teamspace_id: str, work_id: str) -> Externalv1Lightningwork:
        """Fetch a specific Lightning work unit by its ID.

        Args:
            job_id: The unique identifier of the parent job instance.
            teamspace_id: The ID of the teamspace that owns the job.
            work_id: The unique identifier of the work unit to fetch.

        Returns:
            The matching ``Externalv1Lightningwork`` object.
        """
        return self._client.lightningwork_service_get_lightningwork(project_id=teamspace_id, app_id=job_id, id=work_id)

    def get_machine_from_work(self, work: Externalv1Lightningwork, org_id: str) -> Machine:
        """Resolve the ``Machine`` type used by a Lightning work unit from its compute spec.

        Args:
            work: The Lightning work unit whose compute spec is inspected.
            org_id: The organisation ID used to list available accelerators.

        Returns:
            The ``Machine`` enum value that matches the work unit's compute configuration.
        """
        spec: V1LightningworkSpec = work.spec
        # prefer user-requested config if specified
        user_requested_compute_config: V1UserRequestedComputeConfig = spec.user_requested_compute_config
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=work.project_id,
            cloud_account_id=spec.cluster_id,
            org_id=org_id,
        )

        identifiers = []

        if user_requested_compute_config and user_requested_compute_config.name:
            identifiers.append(user_requested_compute_config.name)
        else:
            identifiers.append(spec.compute_config.instance_type)

        for accelerator in accelerators:
            for ident in identifiers:
                if ident in (
                    accelerator.slug,
                    accelerator.slug_multi_cloud,
                    accelerator.instance_id,
                ):
                    return Machine._from_accelerator(accelerator)

        return Machine.from_str(identifiers[0])

    def _get_machines_for_cloud_account(
        self, teamspace_id: str, cloud_account_id: str, org_id: str
    ) -> List[V1ClusterAccelerator]:
        """Return only the enabled accelerators for a given cloud account.

        Args:
            teamspace_id: The ID of the teamspace used for the accelerator lookup.
            cloud_account_id: The cloud account whose accelerators are queried.
            org_id: The organisation ID used for the accelerator lookup.

        Returns:
            A list of ``V1ClusterAccelerator`` objects that are marked as enabled.
        """
        from lightning_sdk.api.cloud_account_api import CloudAccountApi

        cloud_account_api = CloudAccountApi()
        accelerators = cloud_account_api.list_cloud_account_accelerators(
            teamspace_id=teamspace_id,
            cloud_account_id=cloud_account_id,
            org_id=org_id,
        )
        if not accelerators:
            return []

        return list(filter(lambda acc: acc.enabled, accelerators.accelerator))

    def get_studio_name(self, job: Externalv1LightningappInstance) -> str:
        """Return the name of the Studio that launched this v1 job.

        Args:
            job: The v1 job instance whose linked Studio name is resolved.

        Returns:
            The display name of the Studio associated with the job.
        """
        cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
            project_id=job.project_id, id=job.spec.cloud_space_id
        )
        return cs.name

    def submit_job(
        self,
        name: str,
        command: str,
        studio_id: str,
        teamspace_id: str,
        cloud_account: str,
        machine: Union[Machine, str],
        interruptible: bool,
    ) -> Externalv1LightningappInstance:
        """Creates an arbitrary app.

        Args:
            name: The name to assign to the new job.
            command: The shell command the job will execute.
            studio_id: The ID of the Studio from which the job is launched.
            teamspace_id: The ID of the teamspace that will own the job.
            cloud_account: The cloud account identifier to use for compute.
            machine: The machine type (as a ``Machine`` enum or a string slug) to run the job on.
            interruptible: Whether the job may run on interruptible (spot) instances.

        Returns:
            The newly created ``Externalv1LightningappInstance`` object.
        """
        return _create_app(
            self._client,
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type="job",
            compute=_machine_to_compute_name(machine),
            name=name,
            entrypoint=command,
            interruptible=interruptible,
        )

    def get_status_from_work(self, work: Externalv1Lightningwork) -> "Status":
        """Convert a Lightning work unit's internal state to the public ``Status`` enum.

        Args:
            work: The Lightning work unit whose phase is inspected.

        Returns:
            The public ``Status`` value corresponding to the work unit's current phase.
        """
        from lightning_sdk.status import Status

        internal_status = work.status.phase

        if internal_status in (
            V1LightningworkState.UNSPECIFIED,
            V1LightningworkState.IMAGE_BUILDING,
            V1LightningworkState.PENDING,
            V1LightningworkState.NOT_STARTED,
            V1LightningworkState.DELETED,
        ):
            return Status.Pending

        if internal_status == V1LightningworkState.RUNNING:
            return Status.Running

        if internal_status == V1LightningworkState.STOPPED:
            return Status.Stopped

        if internal_status == V1LightningworkState.FAILED:
            return Status.Failed

        return Status.Pending

    def get_logs_finished(self, job_id: str, work_id: str, teamspace_id: str) -> str:
        """Download and return the completed log output for a v1 job work unit.

        Args:
            job_id: The unique identifier of the parent job instance.
            work_id: The unique identifier of the work unit whose logs are fetched.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The decoded log text with datetime prefixes stripped.
        """
        resp: (
            V1DownloadLightningappInstanceLogsResponse
        ) = self._client.lightningapp_instance_service_download_lightningapp_instance_logs(
            project_id=teamspace_id, id=job_id, work_id=work_id
        )

        data = urlopen(resp.url).read().decode("utf-8")
        return remove_datetime_prefix(str(data))

    def get_command(self, job: Externalv1LightningappInstance) -> str:
        """Extract the shell command from the COMMAND env var on a v1 job instance.

        Args:
            job: The v1 job instance from which the command is extracted.

        Returns:
            The value of the ``COMMAND`` environment variable set on the job.

        Raises:
            RuntimeError: If no ``COMMAND`` environment variable is found on the job spec.
        """
        env = job.spec.env

        for e in env:
            if e.name == "COMMAND":
                return e.value

        raise RuntimeError("Could not extract command from app")

    def get_total_cost(self, job: Externalv1LightningappInstance) -> float:
        """Return the accumulated cost for a v1 job in USD.

        Args:
            job: The v1 job instance whose cost is retrieved.

        Returns:
            The total cost incurred by the job, expressed in US dollars.
        """
        status: V1LightningappInstanceStatus = job.status
        return status.total_cost


class JobApiV2:
    """Native (v2 jobs-service) API client for single-machine Jobs."""

    # these are stages the job can be in.
    v2_job_state_pending = "pending"
    v2_job_state_running = "running"
    v2_job_state_stopped = "stopped"
    v2_job_state_completed = "completed"
    v2_job_state_failed = "failed"
    v2_job_state_stopping = "stopping"

    # this is the user action to stop the job.
    v2_job_state_stop = "stop"

    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)

    def submit_job(
        self,
        name: str,
        command: Optional[str],
        cloud_account: Optional[str],
        teamspace_id: str,
        studio_id: Optional[str],
        image: Optional[str],
        machine: Union[Machine, str],
        interruptible: bool,
        env: Optional[Dict[str, str]],
        image_credentials: Optional[str],
        cloud_account_auth: bool,
        entrypoint: str,
        path_mappings: Optional[Dict[str, str]],
        artifacts_local: Optional[str],  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str],  # deprecated in favor of path_mappings
        max_runtime: Optional[int] = None,
        reuse_snapshot: bool = True,
        scratch_disks: Optional[Dict[str, int]] = None,
    ) -> V1Job:
        """Submit a v2 job and return the created job object.

        Args:
            name: The name to assign to the new job.
            command: The shell command the job will execute, or ``None`` when using a custom entrypoint.
            cloud_account: The cloud account identifier to use for compute, or ``None`` to use the default.
            teamspace_id: The ID of the teamspace that will own the job.
            studio_id: The ID of the Studio from which the job is launched, or ``None``.
            image: The container image to run, or ``None`` to use the Studio snapshot.
            machine: The machine type (as a ``Machine`` enum or a string slug) to run the job on.
            interruptible: Whether the job may run on interruptible (spot) instances.
            env: Optional mapping of environment variable names to values.
            image_credentials: Name of the secret holding image-pull credentials, or ``None``.
            cloud_account_auth: Whether to pass cloud-account credentials into the container.
            entrypoint: The entrypoint command used to launch the job process.
            path_mappings: Optional mapping of local paths to remote artifact destinations.
            artifacts_local: Deprecated local artifacts path (use ``path_mappings`` instead).
            artifacts_remote: Deprecated remote artifacts path (use ``path_mappings`` instead).
            max_runtime: Maximum allowed runtime in seconds, or ``None`` for no limit.
            reuse_snapshot: Whether to reuse the Studio's existing filesystem snapshot.
            scratch_disks: Optional mapping of scratch-disk mount paths to their sizes in GiB.

        Returns:
            The newly created ``V1Job`` object.
        """
        if scratch_disks is not None:
            sanitized_scratch_disks = {}
            for k, v in scratch_disks.items():
                sanitized_k = k if k.startswith("/teamspace/scratch/") else f"/teamspace/scratch/{k}"
                sanitized_scratch_disks[sanitized_k] = v
        else:
            sanitized_scratch_disks = None

        body = self._create_job_body(
            name=name,
            command=command,
            cloud_account=cloud_account,
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
            scratch_disks=sanitized_scratch_disks,
        )

        job: V1Job = self._client.jobs_service_create_job(project_id=teamspace_id, body=body)
        return job

    @staticmethod
    def _create_job_body(
        name: str,
        command: Optional[str],
        cloud_account: Optional[str],
        studio_id: Optional[str],
        image: Optional[str],
        machine: Union[Machine, str],
        interruptible: bool,
        env: Optional[Dict[str, str]],
        image_credentials: Optional[str],
        cloud_account_auth: bool,
        entrypoint: str,
        path_mappings: Optional[Dict[str, str]],
        artifacts_local: Optional[str],  # deprecated in favor of path_mappings
        artifacts_remote: Optional[str],  # deprecated in favor of path_mappings)
        reuse_snapshot: bool,
        max_runtime: Optional[int] = None,
        machine_image_version: Optional[str] = None,
        scratch_disks: Optional[Dict[str, int]] = None,
    ) -> JobsServiceCreateJobBody:
        """Build the request body for creating a v2 job.

        Args:
            name: The name to assign to the new job.
            command: The shell command the job will execute, or ``None`` when using a custom entrypoint.
            cloud_account: The cloud account identifier to use for compute, or ``None`` to use the default.
            studio_id: The ID of the Studio from which the job is launched, or ``None``.
            image: The container image to run, or ``None`` to use the Studio snapshot.
            machine: The machine type (as a ``Machine`` enum or a string slug) to run the job on.
            interruptible: Whether the job may run on interruptible (spot) instances.
            env: Optional mapping of environment variable names to values.
            image_credentials: Name of the secret holding image-pull credentials, or ``None``.
            cloud_account_auth: Whether to pass cloud-account credentials into the container.
            entrypoint: The entrypoint command used to launch the job process.
            path_mappings: Optional mapping of local paths to remote artifact destinations.
            artifacts_local: Deprecated local artifacts path (use ``path_mappings`` instead).
            artifacts_remote: Deprecated remote artifacts path (use ``path_mappings`` instead).
            reuse_snapshot: Whether to reuse the Studio's existing filesystem snapshot.
            max_runtime: Maximum allowed runtime in seconds, or ``None`` for no limit.
            machine_image_version: Pinned machine-image version string, or ``None`` for the default.
            scratch_disks: Optional mapping of scratch-disk mount paths to their sizes in GiB.

        Returns:
            A fully populated ``JobsServiceCreateJobBody`` ready to be sent to the jobs service.
        """
        env_vars = []
        if env is not None:
            for k, v in env.items():
                env_vars.append(V1EnvVar(name=k, value=v))

        instance_name = _machine_to_compute_name(machine)

        run_id = __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__[studio_id] if (studio_id is not None and reuse_snapshot) else ""

        path_mappings_list = resolve_path_mappings(
            mappings=path_mappings or {},
            artifacts_local=artifacts_local,
            artifacts_remote=artifacts_remote,
        )

        # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
        optional_spec_kwargs = {}
        if max_runtime:
            optional_spec_kwargs["requested_run_duration_seconds"] = str(max_runtime)

        # don't do default dicts, as they'll be mutable. Create a fresh one here
        scratch_disks = scratch_disks or {}

        spec = V1JobSpec(
            cloudspace_id=studio_id or "",
            cluster_id=cloud_account or "",
            command=command or "",
            entrypoint=entrypoint,
            env=env_vars,
            image=image or "",
            instance_name=instance_name,
            run_id=run_id,
            spot=interruptible,
            image_cluster_credentials=cloud_account_auth,
            image_secret_ref=image_credentials or "",
            path_mappings=path_mappings_list,
            machine_image_version=machine_image_version,
            volumes=[V1Volume(path=k, size_gb=v, ephemeral=True) for k, v in scratch_disks.items()],
            **optional_spec_kwargs,
        )
        return JobsServiceCreateJobBody(name=name, spec=spec)

    def get_job_by_name(self, name: str, teamspace_id: str) -> V1Job:
        """Fetch a v2 job by its unique name within a teamspace.

        Args:
            name: The name of the job to look up.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``V1Job`` object.
        """
        job: V1Job = self._client.jobs_service_find_job(project_id=teamspace_id, name=name)
        return job

    def get_job(self, job_id: str, teamspace_id: str) -> V1Job:
        """Fetch a v2 job by its unique ID.

        Args:
            job_id: The unique identifier of the job to retrieve.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``V1Job`` object.
        """
        job: V1Job = self._client.jobs_service_get_job(project_id=teamspace_id, id=job_id)
        return job

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
        """Request to stop a running v2 job and wait until it reaches a terminal state.

        Args:
            job_id: The unique identifier of the job to stop.
            teamspace_id: The ID of the teamspace that owns the job.
        """
        from lightning_sdk.status import Status

        current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)

        current_state = self._job_state_to_external(current_job.state)

        if current_state in (
            Status.Stopped,
            Status.Completed,
            Status.Failed,
        ):
            return

        if current_state != Status.Stopping:
            update_body = JobsServiceUpdateJobBody(state=self.v2_job_state_stop)
            self._client.jobs_service_update_job(body=update_body, project_id=teamspace_id, id=job_id)

        while True:
            current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)
            if self._job_state_to_external(current_job.state) in (
                Status.Stopped,
                Status.Completed,
                Status.Stopped,
                Status.Failed,
            ):
                break
            time.sleep(1)

    def delete_job(self, job_id: str, teamspace_id: str, cloudspace_id: Optional[str]) -> None:
        """Permanently delete a v2 job.

        Args:
            job_id: The unique identifier of the job to delete.
            teamspace_id: The ID of the teamspace that owns the job.
            cloudspace_id: The ID of the Studio (cloudspace) associated with the job, or ``None``.
        """
        self._client.jobs_service_delete_job(project_id=teamspace_id, id=job_id, cloudspace_id=cloudspace_id or "")

    def get_logs_finished(self, job_id: str, teamspace_id: str) -> str:
        """Download and return the completed log output for a v2 job.

        Args:
            job_id: The unique identifier of the job whose logs are fetched.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The decoded log text with datetime prefixes stripped.
        """
        resp: V1DownloadJobLogsResponse = self._client.jobs_service_download_job_logs(
            project_id=teamspace_id, id=job_id
        )

        data = urlopen(resp.url).read().decode("utf-8")
        return remove_datetime_prefix(str(data))

    def get_studio_name(self, job: V1Job) -> Optional[str]:
        """Return the name of the Studio linked to this job, or ``None`` if none is attached.

        Args:
            job: The v2 job whose linked Studio name is resolved.

        Returns:
            The display name of the Studio, or ``None`` if the job has no associated Studio.
        """
        if job.spec.cloudspace_id:
            cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
                project_id=job.project_id, id=job.spec.cloudspace_id
            )
            return cs.name

        return None

    def get_image_name(self, job: V1Job) -> Optional[str]:
        """Return the container image used by this job, or ``None`` if not set.

        Args:
            job: The v2 job whose image name is retrieved.

        Returns:
            The container image string, or ``None`` if no image was specified.
        """
        return job.spec.image or None

    def get_command(self, job: V1Job) -> str:
        """Return the shell command that the job executes.

        Args:
            job: The v2 job whose command is retrieved.

        Returns:
            The shell command string stored in the job spec.
        """
        return job.spec.command

    def get_mmt_name(self, job: V1Job) -> str:
        """Return the parent multi-machine job name by stripping the machine-index suffix.

        Args:
            job: The v2 job to inspect.

        Returns:
            The parent multi-machine job name derived by removing the trailing index suffix,
            or an empty string if the job is not part of a multi-machine job.
        """
        if job.multi_machine_job_id:
            splits = job.name.rsplit("-", 1)
            if len(splits) == 2:
                return splits[0]
        return ""

    def _job_state_to_external(self, state: str) -> "Status":
        """Convert a raw v2 job state string to the public ``Status`` enum.

        Args:
            state: The raw state string returned by the v2 jobs service.

        Returns:
            The corresponding public ``Status`` enum value, defaulting to ``Status.Pending``
            for any unrecognised state string.
        """
        from lightning_sdk.status import Status

        if state == self.v2_job_state_pending:
            return Status.Pending
        if state == self.v2_job_state_running:
            return Status.Running
        if state == self.v2_job_state_stopped:
            return Status.Stopped
        if state == self.v2_job_state_completed:
            return Status.Completed
        if state == self.v2_job_state_failed:
            return Status.Failed
        if state == self.v2_job_state_stopping:
            return Status.Stopping
        return Status.Pending

    def _get_job_machine_from_spec(self, spec: V1JobSpec, teamspace_id: str, org_id: str) -> "Machine":
        """Resolve the ``Machine`` object from a job spec by matching against available accelerators.

        Args:
            spec: The job spec containing the instance name and cluster identifier.
            teamspace_id: The ID of the teamspace used for the accelerator lookup.
            org_id: The organisation ID used for the accelerator lookup.

        Returns:
            The ``Machine`` enum value that matches the spec's instance, falling back to
            ``Machine.from_str`` if no accelerator record matches.
        """
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=teamspace_id,
            cloud_account_id=spec.cluster_id,
            org_id=org_id,
        )

        for accelerator in accelerators:
            possible_identifiers = (
                accelerator.slug,
                accelerator.slug_multi_cloud,
                accelerator.instance_id,
            )
            if (spec.instance_name and spec.instance_name in possible_identifiers) or (
                spec.instance_type and spec.instance_type in possible_identifiers
            ):
                return Machine._from_accelerator(accelerator)

        return Machine.from_str(spec.instance_name or spec.instance_type)

    def _get_machines_for_cloud_account(
        self, teamspace_id: str, cloud_account_id: str, org_id: str
    ) -> List[V1ClusterAccelerator]:
        """Return only the enabled accelerators for a given cloud account.

        Args:
            teamspace_id: The ID of the teamspace used for the accelerator lookup.
            cloud_account_id: The cloud account whose accelerators are queried.
            org_id: The organisation ID used for the accelerator lookup.

        Returns:
            A list of ``V1ClusterAccelerator`` objects that are marked as enabled.
        """
        from lightning_sdk.api.cloud_account_api import CloudAccountApi

        cloud_account_api = CloudAccountApi()
        accelerators = cloud_account_api.list_cloud_account_accelerators(
            teamspace_id=teamspace_id,
            cloud_account_id=cloud_account_id,
            org_id=org_id,
        )
        if not accelerators:
            return []

        return list(filter(lambda acc: acc.enabled, accelerators.accelerator))

    def get_total_cost(self, job: V1Job) -> float:
        """Return the accumulated cost for a v2 job in USD.

        Args:
            job: The v2 job whose cost is retrieved.

        Returns:
            The total cost incurred by the job, expressed in US dollars.
        """
        return job.total_cost
