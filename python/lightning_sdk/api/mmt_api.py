import time
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from lightning_sdk.api.job_api import V1ClusterAccelerator
from lightning_sdk.api.utils import _get_cloud_url as _cloud_url
from lightning_sdk.api.utils import (
    _machine_to_compute_name,
    resolve_path_mappings,
)
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceCreateMultiMachineJobBody,
    JobsServiceUpdateMultiMachineJobBody,
    V1CloudSpace,
    V1EnvVar,
    V1Job,
    V1JobSpec,
    V1MultiMachineJob,
    V1MultiMachineJobState,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

if TYPE_CHECKING:
    from lightning_sdk.status import Status


class MMTApiV2:
    """Native (v2 jobs-service) API client for multi-machine training jobs."""

    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)

    def submit_job(
        self,
        name: str,
        num_machines: int,
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
        max_runtime: Optional[int],
        reuse_snapshot: bool,
    ) -> V1MultiMachineJob:
        """Submit a v2 multi-machine job and return the created job object.

        Args:
            name: The name to assign to the new multi-machine job.
            num_machines: The number of machines to allocate for the job.
            command: The shell command each machine will execute, or ``None`` when using a custom entrypoint.
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

        Returns:
            The newly created ``V1MultiMachineJob`` object.
        """
        body = self._create_mmt_body(
            name=name,
            num_machines=num_machines,
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
            artifacts_local=artifacts_local,  # deprecated in favor of path_mappings
            artifacts_remote=artifacts_remote,  # deprecated in favor of path_mappings
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
        )

        job: V1MultiMachineJob = self._client.jobs_service_create_multi_machine_job(project_id=teamspace_id, body=body)
        return job

    @staticmethod
    def _create_mmt_body(
        name: str,
        num_machines: int,
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
        artifacts_remote: Optional[str],  # deprecated in favor of path_mappings
        reuse_snapshot: bool,
        max_runtime: Optional[int] = None,
        machine_image_version: Optional[str] = None,
    ) -> JobsServiceCreateMultiMachineJobBody:
        """Build the request body for creating a v2 multi-machine job.

        Args:
            name: The name to assign to the new multi-machine job.
            num_machines: The number of machines to allocate for the job.
            command: The shell command each machine will execute, or ``None`` when using a custom entrypoint.
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

        Returns:
            A fully populated ``JobsServiceCreateMultiMachineJobBody`` ready to be sent to the jobs service.
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
            **optional_spec_kwargs,
        )
        return JobsServiceCreateMultiMachineJobBody(
            name=name, spec=spec, cluster_id=cloud_account or "", machines=num_machines
        )

    def get_job_by_name(self, name: str, teamspace_id: str) -> V1MultiMachineJob:
        """Fetch a multi-machine job by its unique name within a teamspace.

        Args:
            name: The name of the multi-machine job to look up.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``V1MultiMachineJob`` object.
        """
        job: V1MultiMachineJob = self._client.jobs_service_get_multi_machine_job_by_name(
            project_id=teamspace_id, name=name
        )
        return job

    def get_job(self, job_id: str, teamspace_id: str) -> V1MultiMachineJob:
        """Fetch a multi-machine job by its unique ID.

        Args:
            job_id: The unique identifier of the multi-machine job to retrieve.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``V1MultiMachineJob`` object.
        """
        job: V1MultiMachineJob = self._client.jobs_service_get_multi_machine_job(project_id=teamspace_id, id=job_id)
        return job

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
        """Request to stop a running multi-machine job and wait until it reaches a terminal state.

        Args:
            job_id: The unique identifier of the multi-machine job to stop.
            teamspace_id: The ID of the teamspace that owns the job.
        """
        from lightning_sdk.status import Status

        current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)

        current_state = self._job_state_to_external(current_job.desired_state)

        if current_state in (
            Status.Stopped,
            Status.Completed,
            Status.Failed,
        ):
            return

        if current_state != Status.Stopped:
            update_body = JobsServiceUpdateMultiMachineJobBody(desired_state=V1MultiMachineJobState.STOP)
            self._client.jobs_service_update_multi_machine_job(body=update_body, project_id=teamspace_id, id=job_id)

        while True:
            current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)
            if self._job_state_to_external(current_job.state) in (
                Status.Stopping,
                Status.Completed,
                Status.Stopped,
                Status.Failed,
            ):
                break
            time.sleep(1)

    def delete_job(self, job_id: str, teamspace_id: str) -> None:
        """Permanently delete a multi-machine job.

        Args:
            job_id: The unique identifier of the multi-machine job to delete.
            teamspace_id: The ID of the teamspace that owns the job.
        """
        self._client.jobs_service_delete_multi_machine_job(project_id=teamspace_id, id=job_id)

    def list_mmt_subjobs(self, job_id: str, teamspace_id: str) -> List[V1Job]:
        """Return the individual machine sub-jobs that make up a multi-machine job.

        Args:
            job_id: The unique identifier of the parent multi-machine job.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            A list of ``V1Job`` objects representing each per-machine sub-job.
        """
        jobs_resp = self._client.jobs_service_list_jobs(project_id=teamspace_id, multi_machine_job_id=job_id)
        return jobs_resp.jobs

    def _job_state_to_external(self, state: V1MultiMachineJobState) -> "Status":
        """Convert a raw ``V1MultiMachineJobState`` enum value to the public ``Status`` enum.

        Args:
            state: The raw ``V1MultiMachineJobState`` value returned by the jobs service.

        Returns:
            The corresponding public ``Status`` enum value, defaulting to ``Status.Pending``
            for any unrecognised state.
        """
        from lightning_sdk.status import Status

        if str(state) == V1MultiMachineJobState.UNSPECIFIED:
            return Status.Pending
        if str(state) == V1MultiMachineJobState.RUNNING:
            return Status.Running
        if str(state) == V1MultiMachineJobState.STOPPED:
            return Status.Stopped
        if str(state) == V1MultiMachineJobState.COMPLETED:
            return Status.Completed
        if str(state) == V1MultiMachineJobState.FAILED:
            return Status.Failed
        if str(state) == V1MultiMachineJobState.STOP:
            return Status.Stopping
        return Status.Pending

    def get_studio_name(self, job: V1MultiMachineJob) -> Optional[str]:
        """Return the name of the Studio linked to this job, or ``None`` if none is attached.

        Args:
            job: The multi-machine job whose linked Studio name is resolved.

        Returns:
            The display name of the Studio, or ``None`` if the job has no associated Studio.
        """
        if job.spec.cloudspace_id:
            cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
                project_id=job.project_id, id=job.spec.cloudspace_id
            )
            return cs.name

        return None

    def get_image_name(self, job: V1MultiMachineJob) -> Optional[str]:
        """Return the container image used by this job, or ``None`` if not set.

        Args:
            job: The multi-machine job whose image name is retrieved.

        Returns:
            The container image string, or ``None`` if no image was specified.
        """
        return job.spec.image or None

    def get_command(self, job: V1MultiMachineJob) -> str:
        """Return the shell command that the job executes.

        Args:
            job: The multi-machine job whose command is retrieved.

        Returns:
            The shell command string stored in the job spec.
        """
        return job.spec.command

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

    def get_total_cost(self, job: V1MultiMachineJob) -> float:
        """Return the accumulated cost for this multi-machine job in USD.

        Args:
            job: The multi-machine job whose cost is retrieved.

        Returns:
            The total cost incurred by the job, expressed in US dollars.
        """
        return job.total_cost

    def get_num_machines(self, job: V1MultiMachineJob) -> int:
        """Return the number of machines allocated for this multi-machine job.

        Args:
            job: The multi-machine job whose machine count is retrieved.

        Returns:
            The number of machines allocated for the job.
        """
        return job.machines
