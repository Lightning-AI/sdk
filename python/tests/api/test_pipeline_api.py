from unittest.mock import MagicMock, call, patch

import pytest

# Assuming your class is in a file named pipeline_api.py
from lightning_sdk.api.pipeline_api import (
    ApiException,
    PipelineApi,
    PipelinesServiceCreatePipelineBody,
    SchedulesServiceCreateScheduleBody,
    V1DeletePipelineResponse,
    V1Pipeline,
    V1ScheduleResourceType,
    V1SharedFilesystem,
)
from lightning_sdk.pipeline import Schedule

# Constants for testing
PROJECT_ID = "test-project-id"
PIPELINE_ID = "pip_12345"
PIPELINE_NAME = "my-awesome-pipeline"


def _build_pipeline_api(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    api = PipelineApi()
    api._client = mock_client
    return api, mock_client


@patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
@patch("lightning_sdk.api.pipeline_api.LightningClient")
def test_init(mock_client_cls, _mock_cloud_account_api):
    """Test that the LightningClient is initialized with the correct arguments."""
    PipelineApi()
    mock_client_cls.assert_called_once_with(retry=False, max_tries=0)


class TestGetPipelineById:
    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_get_by_id_success(self, mock_client_cls, _mock_cloud_account_api):
        """Test successful retrieval when a pipeline ID is provided."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_get_pipeline.return_value = mock_pipeline

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_ID)

        mock_lightning_client.pipelines_service_get_pipeline.assert_called_once_with(
            project_id=PROJECT_ID, id=PIPELINE_ID
        )
        mock_lightning_client.pipelines_service_get_pipeline_by_name.assert_not_called()
        assert result == mock_pipeline

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_get_by_name_success(self, mock_client_cls, _mock_cloud_account_api):
        """Test successful retrieval when a pipeline name is provided."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_get_pipeline_by_name.return_value = mock_pipeline

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_NAME)

        mock_lightning_client.pipelines_service_get_pipeline_by_name.assert_called_once_with(
            project_id=PROJECT_ID, name=PIPELINE_NAME
        )
        mock_lightning_client.gh.assert_not_called()
        assert result == mock_pipeline

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_get_by_id_not_found(self, mock_client_cls, _mock_cloud_account_api):
        """Test retrieval by ID when the pipeline is not found."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_lightning_client.pipelines_service_get_pipeline.side_effect = ApiException(reason="not found")

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_ID)
        assert result is None

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_get_by_name_not_found(self, mock_client_cls, _mock_cloud_account_api):
        """Test retrieval by name when the pipeline is not found."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_lightning_client.pipelines_service_get_pipeline_by_name.side_effect = ApiException(reason="not found")

        result = pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_NAME)
        assert result is None

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_get_by_id_other_api_error(self, mock_client_cls, _mock_cloud_account_api):
        """Test that other ApiException errors are re-raised."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_lightning_client.pipelines_service_get_pipeline.side_effect = ApiException(reason="server error")

        with pytest.raises(ApiException, match="server error"):
            pipeline_api.get_pipeline_by_id(PROJECT_ID, PIPELINE_ID)


class TestCreatePipeline:
    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_simple(self, mock_client_cls, _mock_cloud_account_api):
        """Test creating a pipeline without schedules or a parent."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        result = pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
            steps=[],
            shared_filesystem=True,
            schedules=[],
            parent_pipeline_id=None,
        )

        # Check that the pipeline was created with correct body
        mock_lightning_client.pipelines_service_create_pipeline.assert_called_once()
        call_args, call_kwargs = mock_lightning_client.pipelines_service_create_pipeline.call_args
        body = call_args[0]
        assert isinstance(body, PipelinesServiceCreatePipelineBody)
        assert body.name == PIPELINE_NAME
        assert body.shared_filesystem.enabled is True
        assert body.parent_pipeline_id == ""
        # stop_on_failure defaults to True, so continue_on_step_failure should be False
        assert body.continue_on_step_failure is False
        assert call_args[1] == PROJECT_ID

        # Ensure no schedule logic was triggered
        mock_lightning_client.schedules_service_list_schedules.assert_not_called()
        mock_lightning_client.schedules_service_delete_schedule.assert_not_called()
        mock_lightning_client.schedules_service_create_schedule.assert_not_called()

        assert result == mock_created_pipeline

    @pytest.mark.parametrize(
        ("stop_on_failure", "expected_continue_on_step_failure"),
        [(True, False), (False, True)],
    )
    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_stop_on_failure(
        self, mock_client_cls, _mock_cloud_account_api, stop_on_failure, expected_continue_on_step_failure
    ):
        """Test that stop_on_failure is mapped to continue_on_step_failure on the body."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
            steps=[],
            shared_filesystem=True,
            schedules=[],
            parent_pipeline_id=None,
            stop_on_failure=stop_on_failure,
        )

        body = mock_lightning_client.pipelines_service_create_pipeline.call_args[0][0]
        assert body.continue_on_step_failure is expected_continue_on_step_failure

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_default_interruption_retries(self, mock_client_cls, _mock_cloud_account_api):
        """Test that interruption_retry_limit defaults to 0 on the body."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
            steps=[],
            shared_filesystem=True,
            schedules=[],
            parent_pipeline_id=None,
        )

        body = mock_lightning_client.pipelines_service_create_pipeline.call_args[0][0]
        assert body.interruption_retry_limit == 0

    @pytest.mark.parametrize("interruption_retries", [0, 1, 5])
    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_interruption_retries(self, mock_client_cls, _mock_cloud_account_api, interruption_retries):
        """Test that interruption_retries is mapped to interruption_retry_limit on the body."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
            steps=[],
            shared_filesystem=True,
            schedules=[],
            parent_pipeline_id=None,
            interruption_retries=interruption_retries,
        )

        body = mock_lightning_client.pipelines_service_create_pipeline.call_args[0][0]
        assert body.interruption_retry_limit == interruption_retries

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_with_schedules(self, mock_client_cls, _mock_cloud_account_api):
        """Test creating a pipeline with new schedules."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        # Use MagicMock for Schedule to avoid needing to import its dependencies
        schedule1 = Schedule(cron_expression="* * * * *", name="daily")
        schedule2 = Schedule(cron_expression="0 0 * * 0", name="weekly")
        schedules = [schedule1, schedule2]

        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
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
        assert isinstance(body1, SchedulesServiceCreateScheduleBody)
        assert body1.cron_expression == "* * * * *"
        assert body1.display_name == "daily"
        assert body1.resource_id == mock_created_pipeline.id
        assert body1.resource_type == V1ScheduleResourceType.PIPELINE

        # Check call 2
        call2_args, _ = mock_lightning_client.schedules_service_create_schedule.call_args_list[1]
        body2 = call2_args[0]
        assert body2.cron_expression == "0 0 * * 0"
        assert body2.display_name == "weekly"

    @pytest.mark.parametrize(
        ("parent_pipeline_id", "expected_parent_resource_id"),
        [
            (None, PIPELINE_ID),
            ("pip_old", "pip_old"),
        ],
    )
    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_schedule_uses_parent_resource_id_for_hierarchy(
        self,
        mock_client_cls,
        _mock_cloud_account_api,
        parent_pipeline_id,
        expected_parent_resource_id,
    ):
        """Schedule create body uses pipeline.id as parent when there is no parent, else the parent id."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline
        mock_lightning_client.schedules_service_list_schedules.return_value = MagicMock(schedules=[])

        schedule = Schedule(cron_expression="0 0 * * *", name="nightly")
        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
            steps=[],
            shared_filesystem=True,
            schedules=[schedule],
            parent_pipeline_id=parent_pipeline_id,
        )

        mock_lightning_client.schedules_service_create_schedule.assert_called_once()
        body, _ = mock_lightning_client.schedules_service_create_schedule.call_args[0]
        assert body.resource_id == PIPELINE_ID
        assert body.parent_resource_id == expected_parent_resource_id

    @patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
    @patch("lightning_sdk.api.pipeline_api.LightningClient")
    def test_create_with_parent_pipeline(self, mock_client_cls, _mock_cloud_account_api):
        """Test creating a pipeline that replaces a parent, deleting old schedules."""
        pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
        parent_id = "pip_old"
        mock_created_pipeline = V1Pipeline(id=PIPELINE_ID, name=PIPELINE_NAME)
        mock_lightning_client.pipelines_service_create_pipeline.return_value = mock_created_pipeline

        # Mock existing schedules that should be deleted
        old_schedule1 = MagicMock(id="sch_old_1")
        old_schedule2 = MagicMock(id="sch_old_2")
        mock_lightning_client.schedules_service_list_schedules.return_value = MagicMock(
            schedules=[old_schedule1, old_schedule2]
        )

        pipeline_api._prepare_shared_filesystem = MagicMock(return_value=V1SharedFilesystem(enabled=True))

        teamspace = MagicMock()
        teamspace.id = PROJECT_ID

        pipeline_api.create_pipeline(
            name=PIPELINE_NAME,
            teamspace=teamspace,
            steps=[],
            shared_filesystem=True,
            schedules=[],  # No new schedules
            parent_pipeline_id=parent_id,
        )

        # Check parent_pipeline_id was passed
        body = mock_lightning_client.pipelines_service_create_pipeline.call_args[0][0]
        assert body.parent_pipeline_id == parent_id

        # Check old schedules were listed by parent pipeline and deleted
        mock_lightning_client.schedules_service_list_schedules.assert_called_once_with(
            PROJECT_ID, parent_resource_id=parent_id
        )

        expected_delete_calls = [
            call(PROJECT_ID, "sch_old_1"),
            call(PROJECT_ID, "sch_old_2"),
        ]
        mock_lightning_client.schedules_service_delete_schedule.assert_has_calls(expected_delete_calls, any_order=True)

        mock_lightning_client.schedules_service_create_schedule.assert_not_called()


@patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
@patch("lightning_sdk.api.pipeline_api.LightningClient")
def test_stop(mock_client_cls, _mock_cloud_account_api):
    """Test the stop method."""
    pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
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


@patch("lightning_sdk.api.pipeline_api.CloudAccountApi")
@patch("lightning_sdk.api.pipeline_api.LightningClient")
def test_delete(mock_client_cls, _mock_cloud_account_api):
    """Test the delete method."""
    pipeline_api, mock_lightning_client = _build_pipeline_api(mock_client_cls)
    mock_response = V1DeletePipelineResponse()
    mock_lightning_client.pipelines_service_delete_pipeline.return_value = mock_response

    result = pipeline_api.delete(PROJECT_ID, PIPELINE_ID)

    mock_lightning_client.pipelines_service_delete_pipeline.assert_called_once_with(PROJECT_ID, PIPELINE_ID)
    assert result == mock_response
