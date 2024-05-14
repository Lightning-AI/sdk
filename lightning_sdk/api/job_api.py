import time
from typing import List

from lightning_sdk.api.utils import _COMPUTE_NAME_TO_MACHINE
from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.lightning_cloud.openapi import (
    AppinstancesIdBody,
    Externalv1LightningappInstance,
    Externalv1Lightningwork,
    V1ComputeConfig,
    V1LightningappInstanceSpec,
    V1LightningappInstanceState,
    V1LightningappInstanceStatus,
    V1LightningworkSpec,
    V1ListLightningworkResponse,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine


class JobApi:
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
