from typing import TYPE_CHECKING, List, Optional

from lightning_sdk.lightning_cloud.openapi.models import (
    ProjectIdPipelinesBody,
    ProjectIdSchedulesBody,
    V1DeletePipelineResponse,
    V1Pipeline,
    V1PipelineStep,
    V1ScheduleResourceType,
    V1SharedFilesystem,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient

if TYPE_CHECKING:
    from lightning_sdk.pipeline.schedule import Schedule


class PipelineApi:
    """Internal API client for Pipeline requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(retry=False, max_tries=0)

    def get_pipeline_by_id(self, project_id: str, pipeline_id_or_name: str) -> Optional[V1Pipeline]:
        if pipeline_id_or_name.startswith("pip_"):
            try:
                return self._client.pipelines_service_get_pipeline(project_id=project_id, id=pipeline_id_or_name)
            except ApiException as ex:
                if "not found" in str(ex):
                    return None
                raise ex
        else:
            try:
                return self._client.pipelines_service_get_pipeline_by_name(
                    project_id=project_id, name=pipeline_id_or_name
                )
            except ApiException as ex:
                if "not found" in str(ex):
                    return None
                raise ex

    def create_pipeline(
        self,
        name: str,
        project_id: str,
        steps: List["V1PipelineStep"],
        shared_filesystem: bool,
        schedules: List["Schedule"],
        parent_pipeline_id: Optional[str],
    ) -> V1Pipeline:
        body = ProjectIdPipelinesBody(
            name=name,
            steps=steps,
            shared_filesystem=V1SharedFilesystem(
                enabled=shared_filesystem,
                s3_folder=True,
            ),
            parent_pipeline_id=parent_pipeline_id or "",
        )

        pipeline = self._client.pipelines_service_create_pipeline(body, project_id)

        # Delete the previous schedules
        if parent_pipeline_id is not None:
            current_schedules = self._client.schedules_service_list_schedules(project_id).schedules
            for schedule in current_schedules:
                self._client.schedules_service_delete_schedule(project_id, schedule.id)

        if len(schedules):
            for schedule in schedules:
                body = ProjectIdSchedulesBody(
                    cron_expression=schedule.cron_expression,
                    display_name=schedule.name,
                    resource_id=pipeline.id,
                    parent_resource_id=parent_pipeline_id or "",
                    resource_type=V1ScheduleResourceType.PIPELINE,
                )

                self._client.schedules_service_create_schedule(body, project_id)

        return pipeline

    def stop(self, pipeline: V1Pipeline) -> V1Pipeline:
        body = pipeline
        body.state = "stop"
        return self._client.pipelines_service_update_pipeline(body)

    def delete(self, project_id: str, pipeline_id: str) -> V1DeletePipelineResponse:
        return self._client.pipelines_service_delete_pipeline(project_id, pipeline_id)
