import time
from typing import TYPE_CHECKING, Dict, Optional

from lightning_sdk.api.utils import (
    _COMPUTE_NAME_TO_MACHINE,
    _MACHINE_TO_COMPUTE_NAME,
)
from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__
from lightning_sdk.lightning_cloud.openapi import (
    MultimachinejobsIdBody,
    ProjectIdMultimachinejobsBody,
    V1EnvVar,
    V1JobSpec,
    V1MultiMachineJob,
    V1MultiMachineJobState,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

if TYPE_CHECKING:
    from lightning_sdk.status import Status


class MMTApi:
    mmt_state_unspecified = "MultiMachineJob_STATE_UNSPECIFIED"
    mmt_state_running = "MultiMachineJob_STATE_RUNNING"
    mmt_state_stopped = "MultiMachineJob_STATE_STOPPED"
    mmt_state_deleted = "MultiMachineJob_STATE_DELETED"
    mmt_state_failed = "MultiMachineJob_STATE_FAILED"
    mmt_state_completed = "MultiMachineJob_STATE_COMPLETED"

    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)

    def submit_job(
        self,
        name: str,
        num_machines: int,
        command: Optional[str],
        cluster_id: Optional[str],
        teamspace_id: str,
        studio_id: Optional[str],
        image: Optional[str],
        machine: Machine,
        interruptible: bool,
        env: Optional[Dict[str, str]],
        image_credentials: Optional[str],
        cluster_auth: bool,
        artifacts_local: Optional[str],
        artifacts_remote: Optional[str],
    ) -> V1MultiMachineJob:
        env_vars = []
        if env is not None:
            for k, v in env.items():
                env_vars.append(V1EnvVar(name=k, value=v))

        instance_name = _MACHINE_TO_COMPUTE_NAME[machine]

        run_id = __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__[studio_id] if studio_id is not None else ""

        spec = V1JobSpec(
            cloudspace_id=studio_id or "",
            cluster_id=cluster_id or "",
            command=command or "",
            env=env_vars,
            image=image or "",
            instance_name=instance_name,
            run_id=run_id,
            spot=interruptible,
            image_cluster_credentials=cluster_auth,
            image_secret_ref=image_credentials or "",
            artifacts_source=artifacts_local or "",
            artifacts_destination=artifacts_remote or "",
        )
        body = ProjectIdMultimachinejobsBody(name=name, spec=spec, cluster_id=cluster_id or "", machines=num_machines)

        job: V1MultiMachineJob = self._client.jobs_service_create_multi_machine_job(project_id=teamspace_id, body=body)
        return job

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
            update_body = MultimachinejobsIdBody(desired_state=self.mmt_state_stopped)
            self._client.jobs_service_update_multi_machine_job(body=update_body, project_id=teamspace_id, id=job_id)

        while True:
            current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)
            if self._job_state_to_external(current_job.desired_state) in (
                Status.Stopped,
                Status.Completed,
                Status.Stopped,
                Status.Failed,
            ):
                break
            time.sleep(1)

    def delete_job(self, job_id: str, teamspace_id: str) -> None:
        self._client.jobs_service_delete_multi_machine_job(project_id=teamspace_id, id=job_id)

    def _job_state_to_external(self, state: V1MultiMachineJobState) -> "Status":
        from lightning_sdk.status import Status

        if str(state) == self.mmt_state_unspecified:
            return Status.Pending
        if str(state) == self.mmt_state_running:
            return Status.Running
        if str(state) == self.mmt_state_stopped:
            return Status.Stopped
        if str(state) == self.mmt_state_completed:
            return Status.Completed
        if str(state) == self.mmt_state_failed:
            return Status.Failed
        return Status.Pending

    def _get_job_machine_from_spec(self, spec: V1JobSpec) -> "Machine":
        instance_name = spec.instance_name
        instance_type = spec.instance_type

        return _COMPUTE_NAME_TO_MACHINE.get(
            instance_type, _COMPUTE_NAME_TO_MACHINE.get(instance_name, instance_type or instance_name)
        )
