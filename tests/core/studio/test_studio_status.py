from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1GetCloudSpaceInstanceStatusResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1Organization,
    V1PluginsListResponse,
    V1Project,
    V1ProjectSettings,
)
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio


def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


@pytest.mark.parametrize(
    ("name", "expected_status"),
    [
        ("st-abc", Status.Pending),
        ("st-def", Status.Pending),
        ("st-ghi", Status.Running),
        ("st-jkl", Status.Failed),
        ("st-mno", Status.Stopping),
        ("st-pqr", Status.Stopped),
        ("st-stu", Status.Stopped),
    ],
)
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
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
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_status(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    name,
    expected_status,
):
    # Setup status side effect based on fixture logic
    def _get_status_side_effect(self, project_id: str, id: str):
        if id == "st-abc":
            status = "CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED"
        elif id == "st-def":
            status = "CLOUD_SPACE_INSTANCE_STATE_PENDING"
        elif id == "st-ghi":
            status = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        elif id == "st-jkl":
            status = "CLOUD_SPACE_INSTANCE_STATE_FAILED"
        elif id == "st-mno":
            status = "CLOUD_SPACE_INSTANCE_STATE_STOPPING"
        elif id == "st-pqr":
            status = "CLOUD_SPACE_INSTANCE_STATE_STOPPED"
        elif id == "st-stu" or id == "st-xyz":
            status = None
        else:
            raise ValueError(f"Invalid {id=}")
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=status))

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
        assert isinstance(body, ProjectIdCloudspacesBody)
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
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.side_effect = _get_status_side_effect
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(name=name, teamspace="ts-abc", org="org-abc", create_ok=True)
    assert studio.status == expected_status
