import warnings
from unittest import mock

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1CloudSpaceInstanceStartupStatus,
    V1GetCloudSpaceInstanceStatusResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1Organization,
    V1PluginsListResponse,
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
@mock.patch("lightning_sdk.api.studio_api.StudioApi.get_tree", autospec=True)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_get_path_info_exists(
    mock_get_teamspace,
    mock_get_org,
    mock_get_tree,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test get_path_info returns correct info for an existing file."""
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
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
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect

    # file exists
    mock_get_tree.return_value = {"tree": [{"path": "test.txt", "type": "blob", "size": 1024}]}

    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.get_path_info("test.txt")

    assert result == {"exists": True, "type": "file", "size": 1024}

    # directory exists
    mock_get_tree.return_value = {"tree": [{"path": "test-dir", "type": "tree", "size": None}]}

    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.get_path_info("test-dir")

    assert result == {"exists": True, "type": "directory", "size": None}

    # directory does not exist
    mock_get_tree.return_value = {"tree": []}

    studio = Studio("st-abc", "ts-abc", "org-abc")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = studio.get_path_info("nonexistent")

        # Check warning was raised
        assert len(w) == 1
        assert "may be empty" in str(w[0].message)

    assert result == {"exists": False, "type": None, "size": None}

    # nested files
    mock_get_tree.return_value = {"tree": [{"path": "data.csv", "type": "blob", "size": 2048}]}

    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.get_path_info("path/to/data.csv")

    assert mock_get_tree.call_args[1]["path"] == "path/to"

    assert result == {"exists": True, "type": "file", "size": 2048}
