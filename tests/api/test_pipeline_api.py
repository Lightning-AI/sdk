from unittest.mock import MagicMock, call, patch

import pytest

# Assuming your class is in a file named pipeline_api.py
from lightning_sdk.api.pipeline_api import (
    ApiException,
    PipelineApi,
    ProjectIdPipelinesBody,
    ProjectIdSchedulesBody,
    V1DeletePipelineResponse,
    V1Pipeline,
    V1ScheduleResourceType,
)
from lightning_sdk.pipeline import Schedule

# Constants for testing
PROJECT_ID = "test-project-id"
PIPELINE_ID = "pip_12345"
PIPELINE_NAME = "my-awesome-pipeline"


@pytest.fixture()
def mock_lightning_client():
    """Fixture to mock the LightningClient, which is a dependency of PipelineApi."""
    # We patch the client where it's *used*, not where it's defined.
    with patch("lightning_sdk.api.pipeline_api.LightningClient") as mock_client_cls:
        # mock_client_cls is the mock of the class itself.
        # We need to configure what happens when it's instantiated.
        mock_client_instance = MagicMock()
        mock_client_cls.return_value = mock_client_instance
        yield mock_client_instance


@pytest.fixture()
def pipeline_api(mock_lightning_client):
    """Fixture to create a PipelineApi instance with a mocked client."""
    # The __init__ of PipelineApi will now use our mocked LightningClient
    api = PipelineApi()
    # This gives tests access to the mocked client instance to check calls
    api._client = mock_lightning_client
    return api


def test_init(mock_lightning_client):
    """Test that the LightningClient is initialized with the correct arguments."""
    # We need to get the mock class, not the instance, to check the constructor call.
    with patch("lightning_sdk.api.pipeline_api.LightningClient") as mock_client_cls:
        PipelineApi()
        mock_client_cls.assert_called_once_with(retry=False, max_tries=0)


class TestGetPipelineById:
    def test_get_by_id_success(self, pipeline_api, mock_lightning_client):
        """Test successful retrieval when a pipeline ID is provided."""
        mock_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_get_pipeline.return_value = mock_pipeline

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_ID)

        mock_lightning_client.pipelines_service_get_pipeline.assert_called_once_with(
            project_id=PROJECT_ID, id=PIPELINE_ID
        )
        mock_lightning_client.pipelines_service_get_pipeline_by_name.assert_not_called()
        assert result == mock_pipeline

    def test_get_by_name_success(self, pipeline_api, mock_lightning_client):
        """Test successful retrieval when a pipeline name is provided."""
        mock_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_get_pipeline_by_name.return_value = mock_pipeline

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_NAME)

        mock_lightning_client.pipelines_service_get_pipeline_by_name.assert_called_once_with(
            project_id=PROJECT_ID, name=PIPELINE_NAME
        )
        mock_lightning_client.gh.assert_not_called()
        assert result == mock_pipeline

    def test_get_by_id_not_found(self, pipeline_api, mock_lightning_client):
        """Test retrieval by ID when the pipeline is not found."""
        mock_lightning_client.pipelines_service_get_pipeline.side_effect = ApiException(reason="not found")

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_ID)
        assert result is None

    def test_get_by_name_not_found(self, pipeline_api, mock_lightning_client):
        """Test retrieval by name when the pipeline is not found."""
        mock_lightning_client.pipelines_service_get_pipeline_by_name.side_effect = ApiException(reason="not found")

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_NAME)
        assert result is None

    def test_get_by_id_other_api_error(self, pipeline_api, mock_lightning_client):
        """Test that other ApiException errors are re-raised."""
        mock_lightning_client.pipelines_service_get_pipeline.side_effect = ApiException(reason="server error")

        with pytest.raises(ApiException, match="server error"):
            pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_ID)


class TestCreatePipeline:
    def test_create_simple(self, pipeline_api, mock_lightning_client):
        """Test creating a pipeline without schedules or a parent."""
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        result = pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            project_id=PROJECT_ID,
            steps=[],
            shared_filesystem=True,
            schedules=[],
            parent_pipeline_id=None,
        )

        # Check that the pipeline was created with correct body
        mock_lightning_client.pipelines_service_create_pipeline.assert_called_once()
        call_args, call_kwargs = mock_lightning_client.pipelines_service_create_pipeline.call_args
        body = call_args[0]
        assert isinstance(body, ProjectIdPipelinesBody)
        assert body.name == PIPELINE_NAME
        assert body.shared_filesystem.enabled is True
        assert body.parent_pipeline_id == ""
        assert call_args[1] == PROJECT_ID

        # Ensure no schedule logic was triggered
        mock_lightning_client.schedules_service_list_schedules.assert_not_called()
        mock_lightning_client.schedules_service_delete_schedule.assert_not_called()
        mock_lightning_client.schedules_service_create_schedule.assert_not_called()

        assert result == mock_created_pipeline

    def test_create_with_schedules(self, pipeline_api, mock_lightning_client):
        """Test creating a pipeline with new schedules."""
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        # Use MagicMock for Schedule to avoid needing to import its dependencies
        schedule1 = Schedule(cron_expression="* * * * *", name="daily")
        schedule2 = Schedule(cron_expression="0 0 * * 0", name="weekly")
        schedules = [schedule1, schedule2]

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            project_id=PROJECT_ID,
            steps=[],
            shared_filesystem=False,
            schedules=schedules,
            parent_pipeline_id=None,
        )

        mock_lightning_client.pipelines_service_create_pipeline.assert_called_once()

        # Check that new schedules are created
        assert mock_lightning_client.schedules_service_create_schedule.call_count == 2

        # Check call 1
        call1_args, _ = mock_lightning_client.schedules_service_create_schedule.call_args_list[0]
        body1 = call1_args[0]
        assert isinstance(body1, ProjectIdSchedulesBody)
        assert body1.cron_expression == "* * * * *"
        assert body1.display_name == "daily"
        assert body1.resource_id == mock_created_pipeline.id
        assert body1.resource_type == V1ScheduleResourceType.PIPELINE

        # Check call 2
        call2_args, _ = mock_lightning_client.schedules_service_create_schedule.call_args_list[1]
        body2 = call2_args[0]
        assert body2.cron_expression == "0 0 * * 0"
        assert body2.display_name == "weekly"

    def test_create_with_parent_pipeline(self, pipeline_api, mock_lightning_client):
        """Test creating a pipeline that replaces a parent, deleting old schedules."""
        parent_id = "pip_old"
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        # Mock existing schedules that should be deleted
        old_schedule1 = MagicMock(id="sch_old_1")
        old_schedule2 = MagicMock(id="sch_old_2")
        mock_lightning_client.schedules_service_list_schedules.return_value = MagicMock(
            schedules=[old_schedule1, old_schedule2]
        )

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            project_id=PROJECT_ID,
            steps=[],
            shared_filesystem=True,
            schedules=[],  # No new schedules
            parent_pipeline_id=parent_id,
        )

        # Check parent_pipeline_id was passed
        body = mock_lightning_client.pipelines_service_create_pipeline.call_args[0][0]
        assert body.parent_pipeline_id == parent_id

        # Check old schedules were listed and deleted
        mock_lightning_client.schedules_service_list_schedules.assert_called_once_with(PROJECT_ID)

        expected_delete_calls = [
            call(PROJECT_ID, "sch_old_1"),
            call(PROJECT_ID, "sch_old_2"),
        ]
        mock_lightning_client.schedules_service_delete_schedule.assert_has_calls(expected_delete_calls, any_order=True)

        mock_lightning_client.schedules_service_create_schedule.assert_not_called()


def test_stop(pipeline_api, mock_lightning_client):
    """Test the stop method."""
    # Create a mock pipeline object. V1Pipeline has a __setattr__ that needs to be handled
    # by using a real object or a more careful mock. Using a real object is easier.
    pipeline_to_stop = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME, state="running")

    mock_stopped_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME, state="stop")
    mock_lightning_client.pipelines_service_update_pipeline.return_value = mock_stopped_pipeline

    result = pipeline_api.stop(pipeline_to_stop)

    # Check that the state was updated *before* the call
    # The `update_pipeline` method should be called with the modified object
    call_args, _ = mock_lightning_client.pipelines_service_update_pipeline.call_args
    updated_pipeline_body = call_args[0]

    assert updated_pipeline_body.state == "stop"

    # Verify the correct client method was called
    mock_lightning_client.pipelines_service_update_pipeline.assert_called_once_with(updated_pipeline_body)

    # Verify the result is passed through
    assert result == mock_stopped_pipeline


def test_delete(pipeline_api, mock_lightning_client):
    """Test the delete method."""
    mock_response = V1DeletePipelineResponse()
    mock_lightning_client.pipelines_service_delete_pipeline.return_value = mock_response

    result = pipeline_api.delete(PROJECT_ID, PIPELINE_ID)

    mock_lightning_client.pipelines_service_delete_pipeline.assert_called_once_with(PROJECT_ID, PIPELINE_ID)
    assert result == mock_response
