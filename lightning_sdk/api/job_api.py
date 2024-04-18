from lightning_sdk.api.utils import (
    _get_cloud_url as _cloud_url,
)
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
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
            return status.state
        return None
