import time
from unittest import mock

import pytest

from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceCreateCloudSpaceBody,
    Externalv1CloudSpaceInstanceStatus,
    V1CloudSpace,
    V1CloudSpaceInstanceStartupStatus,
    V1ExecuteCloudSpaceCommandResponse,
    V1GetCloudSpaceInstanceStatusResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1Organization,
    V1Project,
    V1ProjectSettings,
)
from lightning_sdk.studio import Studio


def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


class _DummyResponse:
    data: bytes


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_run_command(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted")

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.run("foo", "bar")

    assert result == "foo-response bar-response"


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_run_command_error(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Submitted Successfully")

    resp = _DummyResponse
    resp.data = b'{"result":{"output":" No such file or directory foo ","exitCode":1}}\n'
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    studio = Studio("st-abc", "ts-abc", "org-abc")

    with pytest.raises(RuntimeError, match="No such file or directory foo"):
        studio.run("foo", "bar")


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_run_command_exit_code(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted")

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    studio = Studio("st-abc", "ts-abc", "org-abc")

    result_output, result_exit_code = studio.run_with_exit_code("foo", "bar")

    assert result_output == "foo-response bar-response"
    assert result_exit_code == 0


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_run_command_and_detach(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted")

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    with mock.patch(
        "lightning_sdk.api.studio_api.StudioApi._get_detached_command_status"
    ) as mock_get_detached_command_status:

        def side_effect(studio_id, teamspace_id, session_id):
            time.sleep(1)
            yield

        mock_get_detached_command_status.side_effect = side_effect
        api = StudioApi()
        # should return immediately
        iterator = api.run_studio_commands_and_yield("st-abc", "ts-abc", "foo", timeout=0, check_interval=0)
        with pytest.raises(StopIteration):
            next(iterator)
