import time

from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.lightning_cloud.openapi import (
    AppinstancesIdBody,
    Externalv1LightningappInstance,
    V1LightningappInstanceSpec,
    V1LightningappInstanceState,
    V1LightningappInstanceStatus,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class JobApi:
    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=3)

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
