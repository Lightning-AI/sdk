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
    AppinstancesIdBody,
    Externalv1LightningappInstance,
    Externalv1Lightningwork,
    JobsIdBody1,
    ProjectIdJobsBody,
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
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

if TYPE_CHECKING:
    from lightning_sdk.status import Status


class JobApiV1:
    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)

    def get_job(self, job_name: str, teamspace_id: str) -> Externalv1LightningappInstance:
        try:
            return self._client.lightningapp_instance_service_find_lightningapp_instance(
                project_id=teamspace_id, name=job_name
            )

        except Exception:
            raise ValueError(f"Job {job_name} does not exist") from None

    def get_job_status(self, job_id: str, teamspace_id: str) -> V1LightningappInstanceState:
        instance = self._client.lightningapp_instance_service_get_lightningapp_instance(
            project_id=teamspace_id, id=job_id
        )

        status: V1LightningappInstanceStatus = instance.status

        if status is not None:
            return status.phase
        return None

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
        body = AppinstancesIdBody(spec=V1LightningappInstanceSpec(desired_state=V1LightningappInstanceState.STOPPED))
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
        self._client.lightningapp_instance_service_delete_lightningapp_instance(project_id=teamspace_id, id=job_id)

    def list_works(self, job_id: str, teamspace_id: str) -> List[Externalv1Lightningwork]:
        resp: V1ListLightningworkResponse = self._client.lightningwork_service_list_lightningwork(
            project_id=teamspace_id, app_id=job_id
        )
        return resp.lightningworks

    def get_work(self, job_id: str, teamspace_id: str, work_id: str) -> Externalv1Lightningwork:
        return self._client.lightningwork_service_get_lightningwork(project_id=teamspace_id, app_id=job_id, id=work_id)

    def get_machine_from_work(self, work: Externalv1Lightningwork, org_id: str) -> Machine:
        spec: V1LightningworkSpec = work.spec
        # prefer user-requested config if specified
        user_requested_compute_config: V1UserRequestedComputeConfig = spec.user_requested_compute_config
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=work.project_id,
            cloud_account_id=spec.cluster_id,
            org_id=org_id,
        )

        identifier = None

        if user_requested_compute_config and user_requested_compute_config.name:
            identifier = user_requested_compute_config.name
        else:
            identifier = spec.compute_config.instance_type

        for accelerator in accelerators:
            if identifier in (
                accelerator.slug,
                accelerator.slug_multi_cloud,
                accelerator.instance_id,
            ):
                return Machine.from_str(accelerator.slug_multi_cloud)

        return Machine.from_str(identifier)

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

    def get_studio_name(self, job: Externalv1LightningappInstance) -> str:
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
        """Creates an arbitrary app."""
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
        resp: (
            V1DownloadLightningappInstanceLogsResponse
        ) = self._client.lightningapp_instance_service_download_lightningapp_instance_logs(
            project_id=teamspace_id, id=job_id, work_id=work_id
        )

        data = urlopen(resp.url).read().decode("utf-8")
        return remove_datetime_prefix(str(data))

    def get_command(self, job: Externalv1LightningappInstance) -> str:
        env = job.spec.env

        for e in env:
            if e.name == "COMMAND":
                return e.value

        raise RuntimeError("Could not extract command from app")

    def get_total_cost(self, job: Externalv1LightningappInstance) -> float:
        status: V1LightningappInstanceStatus = job.status
        return status.total_cost


class JobApiV2:
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
    ) -> V1Job:
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
        max_runtime: Optional[int] = None,
        machine_image_version: Optional[str] = None,
    ) -> ProjectIdJobsBody:
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
        return ProjectIdJobsBody(name=name, spec=spec)

    def get_job_by_name(self, name: str, teamspace_id: str) -> V1Job:
        job: V1Job = self._client.jobs_service_find_job(project_id=teamspace_id, name=name)
        return job

    def get_job(self, job_id: str, teamspace_id: str) -> V1Job:
        job: V1Job = self._client.jobs_service_get_job(project_id=teamspace_id, id=job_id)
        return job

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
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
            update_body = JobsIdBody1(state=self.v2_job_state_stop)
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
        self._client.jobs_service_delete_job(project_id=teamspace_id, id=job_id, cloudspace_id=cloudspace_id or "")

    def get_logs_finished(self, job_id: str, teamspace_id: str) -> str:
        resp: V1DownloadJobLogsResponse = self._client.jobs_service_download_job_logs(
            project_id=teamspace_id, id=job_id
        )

        data = urlopen(resp.url).read().decode("utf-8")
        return remove_datetime_prefix(str(data))

    def get_studio_name(self, job: V1Job) -> Optional[str]:
        if job.spec.cloudspace_id:
            cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
                project_id=job.project_id, id=job.spec.cloudspace_id
            )
            return cs.name

        return None

    def get_image_name(self, job: V1Job) -> Optional[str]:
        return job.spec.image or None

    def get_command(self, job: V1Job) -> str:
        return job.spec.command

    def get_mmt_name(self, job: V1Job) -> str:
        if job.multi_machine_job_id:
            splits = job.name.rsplit("-", 1)
            if len(splits) == 2:
                return splits[0]
        return ""

    def _job_state_to_external(self, state: str) -> "Status":
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

    def get_total_cost(self, job: V1Job) -> float:
        return job.total_cost
