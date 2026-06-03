from typing import TYPE_CHECKING, List, Optional, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.lightning_cloud.openapi.models import (
    PipelinesServiceCreatePipelineBody,
    SchedulesServiceCreateScheduleBody,
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
        """Fetch a pipeline by its ID (prefix ``pip_``) or by name; returns ``None`` if not found.

        Args:
            project_id: The teamspace ID that owns the pipeline.
            pipeline_id_or_name: A pipeline ID (starting with ``pip_``) or a pipeline name.

        Returns:
            Optional[V1Pipeline]: The matching pipeline, or ``None`` if not found.

        Raises:
            ApiException: If the API returns an unexpected error.
        """
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
        stop_on_failure: bool = True,
    ) -> V1Pipeline:
        """Create a pipeline with the given steps and schedules, replacing the parent pipeline's schedules if provided.

        Args:
            name: Display name for the new pipeline.
            teamspace: The teamspace to create the pipeline in.
            steps: Ordered list of pipeline steps.
            shared_filesystem: Whether to enable a shared filesystem between steps.
            schedules: List of schedules to attach to the pipeline.
            parent_pipeline_id: ID of an existing pipeline whose schedules should be replaced.
            stop_on_failure: Whether the pipeline execution should stop if any step fails. Defaults to True.

        Returns:
            V1Pipeline: The created pipeline record.
        """
        body = PipelinesServiceCreatePipelineBody(
            name=name,
            steps=steps,
            shared_filesystem=self._prepare_shared_filesystem(shared_filesystem, steps, teamspace),
            parent_pipeline_id=parent_pipeline_id or "",
            continue_on_step_failure=not stop_on_failure,
        )

        pipeline = self._client.pipelines_service_create_pipeline(body, teamspace.id)

        # Delete the previous schedules
        if parent_pipeline_id is not None:
            current_schedules = self._client.schedules_service_list_schedules(
                teamspace.id, parent_resource_id=parent_pipeline_id
            ).schedules
            for schedule in current_schedules:
                self._client.schedules_service_delete_schedule(teamspace.id, schedule.id)

        if len(schedules):
            for schedule in schedules:
                body = SchedulesServiceCreateScheduleBody(
                    cron_expression=schedule.cron_expression,
                    display_name=schedule.name,
                    resource_id=pipeline.id,
                    parent_resource_id=parent_pipeline_id or pipeline.id,
                    resource_type=V1ScheduleResourceType.PIPELINE,
                    timezone=schedule.timezone,
                    parallel_runs=schedule.parallel_runs or False,
                )

                self._client.schedules_service_create_schedule(body, teamspace.id)

        return pipeline

    def stop(self, pipeline: V1Pipeline) -> V1Pipeline:
        """Request to stop a running pipeline.

        Args:
            pipeline: The pipeline to stop.

        Returns:
            V1Pipeline: The updated pipeline record after the stop request.
        """
        body = pipeline
        body.state = "stop"
        return self._client.pipelines_service_update_pipeline(body)

    def delete(self, project_id: str, pipeline_id: str) -> V1DeletePipelineResponse:
        """Permanently delete a pipeline.

        Args:
            project_id: The teamspace ID that owns the pipeline.
            pipeline_id: The unique ID of the pipeline to delete.

        Returns:
            V1DeletePipelineResponse: The deletion response from the server.
        """
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
