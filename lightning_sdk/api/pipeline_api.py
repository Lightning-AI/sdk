from typing import TYPE_CHECKING, List, Optional, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
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
from lightning_sdk.teamspace import Teamspace

if TYPE_CHECKING:
    from lightning_sdk.pipeline.schedule import Schedule


class PipelineApi:
    """Internal API client for Pipeline requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=0, retry=False)
        self._cloud_account_api = CloudAccountApi()

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
        teamspace: Teamspace,
        steps: List["V1PipelineStep"],
        shared_filesystem: bool,
        schedules: List["Schedule"],
        parent_pipeline_id: Optional[str],
    ) -> V1Pipeline:
        body = ProjectIdPipelinesBody(
            name=name,
            steps=steps,
            shared_filesystem=self._prepare_shared_filesystem(shared_filesystem, steps, teamspace),
            parent_pipeline_id=parent_pipeline_id or "",
        )

        pipeline = self._client.pipelines_service_create_pipeline(body, teamspace.id)

        # Delete the previous schedules
        if parent_pipeline_id is not None:
            current_schedules = self._client.schedules_service_list_schedules(teamspace.id).schedules
            for schedule in current_schedules:
                self._client.schedules_service_delete_schedule(teamspace.id, schedule.id)

        if len(schedules):
            for schedule in schedules:
                body = ProjectIdSchedulesBody(
                    cron_expression=schedule.cron_expression,
                    display_name=schedule.name,
                    resource_id=pipeline.id,
                    parent_resource_id=parent_pipeline_id or "",
                    resource_type=V1ScheduleResourceType.PIPELINE,
                    timezone=schedule.timezone,
                    parallel_runs=schedule.parallel_runs or False,
                )

                self._client.schedules_service_create_schedule(body, teamspace.id)

        return pipeline

    def stop(self, pipeline: V1Pipeline) -> V1Pipeline:
        body = pipeline
        body.state = "stop"
        return self._client.pipelines_service_update_pipeline(body)

    def delete(self, project_id: str, pipeline_id: str) -> V1DeletePipelineResponse:
        return self._client.pipelines_service_delete_pipeline(project_id, pipeline_id)

    def _prepare_shared_filesystem(
        self, shared_filesystem: Union[bool, V1SharedFilesystem], steps: List["V1PipelineStep"], teamspace: Teamspace
    ) -> V1SharedFilesystem:
        if not shared_filesystem:
            return V1SharedFilesystem(enabled=False)

        from lightning_sdk.pipeline.utils import _get_cloud_account

        clusters = self._cloud_account_api.list_cloud_accounts(teamspace_id=teamspace.id)

        selected_cluster = None
        selected_cluster_id = _get_cloud_account(steps)
        for cluster in clusters:
            if cluster.id == selected_cluster_id:
                selected_cluster = cluster
                break

        if selected_cluster is None:
            raise ValueError(f"Cloud Account {selected_cluster_id} not found")

        if selected_cluster.spec.aws_v1:
            return V1SharedFilesystem(enabled=True, s3_folder=True)

        if selected_cluster.spec.google_cloud_v1:
            return V1SharedFilesystem(enabled=True, gcs_folder=True)

        raise NotImplementedError("This cluster isn't support yet")
