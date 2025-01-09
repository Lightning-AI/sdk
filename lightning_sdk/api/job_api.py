import time
from typing import TYPE_CHECKING, Dict, List, Optional
from urllib.request import urlopen

from lightning_sdk.api.utils import (
    _COMPUTE_NAME_TO_MACHINE,
    _MACHINE_TO_COMPUTE_NAME,
    _create_app,
    remove_datetime_prefix,
)
from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__
from lightning_sdk.lightning_cloud.openapi import (
    AppinstancesIdBody,
    Externalv1LightningappInstance,
    Externalv1Lightningwork,
    JobsIdBody1,
    ProjectIdJobsBody,
    V1CloudSpace,
    V1ComputeConfig,
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

    def get_machine_from_work(self, work: Externalv1Lightningwork) -> Machine:
        spec: V1LightningworkSpec = work.spec
        # prefer user-requested config if specified
        compute_config: V1UserRequestedComputeConfig = spec.user_requested_compute_config
        compute: str = compute_config.name
        if compute:
            return _COMPUTE_NAME_TO_MACHINE[compute]
        compute_config: V1ComputeConfig = spec.compute_config
        compute: str = compute_config.instance_type
        return _COMPUTE_NAME_TO_MACHINE[compute]

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
        machine: Machine,
        interruptible: bool,
    ) -> Externalv1LightningappInstance:
        """Creates an arbitrary app."""
        return _create_app(
            self._client,
            studio_id=studio_id,
            teamspace_id=teamspace_id,
            cloud_account=cloud_account,
            plugin_type="job",
            compute=_MACHINE_TO_COMPUTE_NAME[machine],
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


class JobApiV2:
    v2_job_state_pending = "pending"
    v2_job_state_running = "running"
    v2_job_state_stopped = "stopped"
    v2_job_state_completed = "completed"
    v2_job_state_failed = "failed"
    v2_job_state_stopping = "stopping"

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
        machine: Machine,
        interruptible: bool,
        env: Optional[Dict[str, str]],
        image_credentials: Optional[str],
        cloud_account_auth: bool,
        artifacts_local: Optional[str],
        artifacts_remote: Optional[str],
    ) -> V1Job:
        env_vars = []
        if env is not None:
            for k, v in env.items():
                env_vars.append(V1EnvVar(name=k, value=v))

        instance_name = _MACHINE_TO_COMPUTE_NAME[machine]

        run_id = __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__[studio_id] if studio_id is not None else ""

        spec = V1JobSpec(
            cloudspace_id=studio_id or "",
            cluster_id=cloud_account or "",
            command=command or "",
            env=env_vars,
            image=image or "",
            instance_name=instance_name,
            run_id=run_id,
            spot=interruptible,
            image_cluster_credentials=cloud_account_auth,
            image_secret_ref=image_credentials or "",
            artifacts_source=artifacts_local or "",
            artifacts_destination=artifacts_remote or "",
        )
        body = ProjectIdJobsBody(name=name, spec=spec)

        job: V1Job = self._client.jobs_service_create_job(project_id=teamspace_id, body=body)
        return job

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
            update_body = JobsIdBody1(cloudspace_id=current_job.spec.cloudspace_id, state=self.v2_job_state_stopped)
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

    def get_studio_name(self, job: V1Job) -> str:
        cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
            project_id=job.project_id, id=job.spec.cloudspace_id
        )
        return cs.name

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

    def _get_job_machine_from_spec(self, spec: V1JobSpec) -> "Machine":
        instance_name = spec.instance_name
        instance_type = spec.instance_type

        return _COMPUTE_NAME_TO_MACHINE.get(
            instance_type, _COMPUTE_NAME_TO_MACHINE.get(instance_name, instance_type or instance_name)
        )
