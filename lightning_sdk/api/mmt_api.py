import json
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from lightning_sdk.api.job_api import JobApiV1, V1ClusterAccelerator
from lightning_sdk.api.utils import (
    _create_app,
    _machine_to_compute_name,
    resolve_path_mappings,
)
from lightning_sdk.api.utils import _get_cloud_url as _cloud_url
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    MultimachinejobsIdBody,
    ProjectIdMultimachinejobsBody,
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


class MMTApiV1(JobApiV1):
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
        studio_id: str,
        machine: Union[Machine, str],
        interruptible: bool,
        strategy: str,
    ) -> Externalv1LightningappInstance:
        """Creates a multi-machine job with given commands."""
        distributed_args = {
            "cloud_compute": _machine_to_compute_name(machine),
            "num_instances": num_machines,
            "strategy": strategy,
        }
        return _create_app(
            client=self._client,
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account or "",
            plugin_type="distributed_plugin",
            entrypoint=command,
            name=name,
            distributedArguments=json.dumps(distributed_args),
            interruptible=interruptible,
        )


class MMTApiV2:
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
    ) -> V1MultiMachineJob:
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
        max_runtime: Optional[int] = None,
        machine_image_version: Optional[str] = None,
    ) -> ProjectIdMultimachinejobsBody:
        env_vars = []
        if env is not None:
            for k, v in env.items():
                env_vars.append(V1EnvVar(name=k, value=v))

        instance_name = _machine_to_compute_name(machine)

        run_id = __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__[studio_id] if studio_id is not None else ""

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
        return ProjectIdMultimachinejobsBody(
            name=name, spec=spec, cluster_id=cloud_account or "", machines=num_machines
        )

    def get_job_by_name(self, name: str, teamspace_id: str) -> V1MultiMachineJob:
        job: V1MultiMachineJob = self._client.jobs_service_get_multi_machine_job_by_name(
            project_id=teamspace_id, name=name
        )
        return job

    def get_job(self, job_id: str, teamspace_id: str) -> V1MultiMachineJob:
        job: V1MultiMachineJob = self._client.jobs_service_get_multi_machine_job(project_id=teamspace_id, id=job_id)
        return job

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
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
            update_body = MultimachinejobsIdBody(desired_state=V1MultiMachineJobState.STOP)
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
        self._client.jobs_service_delete_multi_machine_job(project_id=teamspace_id, id=job_id)

    def list_mmt_subjobs(self, job_id: str, teamspace_id: str) -> List[V1Job]:
        jobs_resp = self._client.jobs_service_list_jobs(project_id=teamspace_id, multi_machine_job_id=job_id)
        return jobs_resp.jobs

    def _job_state_to_external(self, state: V1MultiMachineJobState) -> "Status":
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
        if job.spec.cloudspace_id:
            cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
                project_id=job.project_id, id=job.spec.cloudspace_id
            )
            return cs.name

        return None

    def get_image_name(self, job: V1MultiMachineJob) -> Optional[str]:
        return job.spec.image or None

    def get_command(self, job: V1MultiMachineJob) -> str:
        return job.spec.command

    def _get_job_machine_from_spec(self, spec: V1JobSpec, teamspace_id: str, org_id: str) -> "Machine":
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
                return Machine.from_str(accelerator.slug_multi_cloud)

        return Machine.from_str(spec.instance_name or spec.instance_type)

    def _get_machines_for_cloud_account(
        self, teamspace_id: str, cloud_account_id: str, org_id: str
    ) -> List[V1ClusterAccelerator]:
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
        return job.total_cost

    def get_num_machines(self, job: V1MultiMachineJob) -> int:
        return job.machines
