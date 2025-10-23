from unittest import mock

from lightning_sdk.lightning_cloud.openapi import (
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1Organization,
    V1PluginsListResponse,
    V1Project,
    V1ProjectSettings,
)
from lightning_sdk.machine import Machine
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
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_duplicate_machine(
    mock_get_teamspace,
    mock_get_org,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks
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

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc", start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    studio._studio_api = mock.MagicMock()
    studio._studio_api.duplicate_studio.return_value = {
        "name": "st-abc",
        "teamspace": "ts-abc",
        "org": "org-abc",
    }

    studio.duplicate(machine=Machine.A100)
    studio._studio_api.duplicate_studio.assert_called_once_with(
        studio_id="st-abc",
        teamspace_id="ts-abc",
        target_teamspace_id="ts-abc",
        machine=Machine.A100,
        new_name=None,
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
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_duplicate_with_new_name(
    mock_get_teamspace,
    mock_get_org,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks
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

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc", start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    studio._studio_api = mock.MagicMock()
    studio._studio_api.duplicate_studio.return_value = {
        "name": "my-new-studio-name",
        "teamspace": "ts-abc",
        "org": "org-abc",
    }

    studio.duplicate(machine=Machine.CPU, name="my-new-studio-name")

    studio._studio_api.duplicate_studio.assert_called_once_with(
        studio_id="st-abc",
        teamspace_id="ts-abc",
        target_teamspace_id="ts-abc",
        machine=Machine.CPU,
        new_name="my-new-studio-name",
    )
