from typing import List

from lightning_sdk.lightning_cloud.openapi.models import (
    ProjectIdPipelinesBody,
    V1Pipeline,
    V1PipelineStep,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class PipelineApi:
    """Internal API client for Pipeline requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def get_pipeline_by_id(self, project_id: str, pipeline_id: str) -> V1Pipeline:
        try:
            return self._client.jobs_service_get_deployment(project_id=project_id, id=pipeline_id)
        except ApiException as ex:
            if "Reason: Not Found" in str(ex):
                return None
            raise ex

    def create_pipeline(
        self,
        name: str,
        project_id: str,
        steps: List["V1PipelineStep"],
    ) -> V1Pipeline:
        body = ProjectIdPipelinesBody(
            name=name,
            steps=steps,
        )
        return self._client.pipelines_service_create_pipeline(body, project_id)
