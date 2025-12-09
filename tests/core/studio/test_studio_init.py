import os
from contextlib import nullcontext
from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceCreateCloudSpaceBody,
    Externalv1CloudSpaceInstanceStatus,
    V1AWSDirectV1,
    V1CloudSpace,
    V1ClusterType,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GoogleCloudDirectV1,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListClustersResponse,
    V1ListProjectClustersResponse,
    V1Organization,
    V1PluginsListResponse,
    V1Project,
    V1ProjectSettings,
)
from lightning_sdk.machine import CloudProvider
from lightning_sdk.studio import Studio


def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


@pytest.mark.parametrize("create_ok", [True, False])
@pytest.mark.parametrize("cluster", [None, "c-abc"])
@pytest.mark.parametrize("name", ["st-abc", "st-xyz"])
@pytest.mark.parametrize("studio_type", [None, "python"])
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
@mock.patch("lightning_sdk.studio.BaseStudio", autospec=True)
def test_studio_init(
    mock_base_studio,
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
    cluster,
    create_ok,
    studio_type,
):
    # Setup mocks
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

    def _get_status_side_effect(*args, **kwargs):
        id = kwargs.get("id")
        if id == "st-abc":
            status = "CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED"
        elif id == "st-def":
            status = "CLOUD_SPACE_INSTANCE_STATE_PENDING"
        else:
            status = None
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=status))

    # Setup teamspace mock
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    # Setup organization mock
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    # Setup plugin mocks
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    # Setup cloud space service mocks
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_status.side_effect = _get_status_side_effect

    # Setup studio type
    mock_base_studio_instance = mock.MagicMock()
    mock_studio_type = mock.MagicMock()
    mock_studio_type.id = "python"
    mock_studio_type.name = "Python"
    mock_base_studio_instance.list.return_value = [mock_studio_type]
    mock_base_studio.return_value = mock_base_studio_instance

    # st-xyz does not exist and should not be created
    error_out = bool(name == "st-xyz" and not create_ok)
    contextman = pytest.raises(ValueError, match="Studio st-xyz does not exist") if error_out else nullcontext()

    with contextman:
        studio = Studio(
            name=name,
            teamspace="ts-abc",
            org="org-abc",
            cloud_account=cluster,
            create_ok=create_ok,
            studio_type=studio_type,
        )

    if error_out:
        return

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"
    assert studio.name == name


@mock.patch.dict(os.environ, {"LIGHTNING_TEAMSPACE": ""}, clear=False)
@mock.patch("lightning_sdk.utils.config.Config.get_value")
@mock.patch("lightning_sdk.studio._resolve_teamspace")
def test_studio_init_no_teamspace(mock_resolve_teamspace, mock_config_get_value):
    # Mock config to return None for teamspace_name
    mock_config_get_value.return_value = None
    # Mock _resolve_teamspace to return None, which should trigger the ValueError
    mock_resolve_teamspace.return_value = None

    with pytest.raises(ValueError, match="Couldn't resolve teamspace from the provided name, org, or user"):
        Studio(
            name="st-xyz",
        )


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_SPACE_ID": "st-current"}, clear=False)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_init_detects_current_studio_from_env(
    mock_get_teamspace,
    mock_get_org,
    mock_get_cloud_space,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test that Studio.__init__ detects current studio from LIGHTNING_CLOUD_SPACE_ID env var."""
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc",
            display_name="st-abc",
            cluster_id="c-abc",
            project_id="ts-abc",
            id="st-abc",
            environment_template_id="python-template",
        ),
        "st-current": V1CloudSpace(
            name="st-current",
            display_name="st-current",
            cluster_id="c-def",
            project_id="ts-abc",
            id="st-current",
            environment_template_id="data-template",
        ),
    }

    def _get_cloud_space_side_effect(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return existing_studios.get(id)

    def _get_status_side_effect(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=None))

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc"),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_get_cloud_space.side_effect = _get_cloud_space_side_effect
    mock_get_status.side_effect = _get_status_side_effect

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    mock_get_cloud_space.assert_called()
    call_args_list = [
        call
        for call in mock_get_cloud_space.call_args_list
        if call[1].get("id") == "st-current" or (len(call[0]) > 2 and call[0][2] == "st-current")
    ]
    assert len(call_args_list) > 0, "get_cloud_space should have been called with st-current"

    assert studio.name == "st-abc"
    assert studio.cloud_account == "c-abc"


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_SPACE_ID": "st-current"}, clear=False)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_init_uses_current_studio_cloud_account(
    mock_get_teamspace,
    mock_get_org,
    mock_get_cloud_space,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test that Studio.__init__ uses current studio's cloud_account when no cloud_account is specified."""
    existing_studios = {
        "st-current": V1CloudSpace(
            name="st-current",
            display_name="st-current",
            cluster_id="c-from-current",
            project_id="ts-abc",
            id="st-current",
        ),
    }

    def _get_cloud_space_side_effect(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return existing_studios.get(id)

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _get_status_side_effect(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=None))

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-default"),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-default"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_get_cloud_space.side_effect = _get_cloud_space_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_get_status.side_effect = _get_status_side_effect

    studio = Studio(name="st-new", teamspace="ts-abc", org="org-abc", create_ok=True)

    assert studio.name == "st-new"
    mock_get_cloud_space.assert_called()


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_SPACE_ID": "st-current"}, clear=False)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_init_uses_current_studio_template(
    mock_get_teamspace,
    mock_get_org,
    mock_get_cloud_space,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test that Studio.__init__ uses current studio's environment_template_id when no studio_type is specified."""
    existing_studios = {
        "st-current": V1CloudSpace(
            name="st-current",
            display_name="st-current",
            cluster_id="c-abc",
            project_id="ts-abc",
            id="st-current",
            environment_template_id="python-template-id",
        ),
    }

    def _get_cloud_space_side_effect(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return existing_studios.get(id)

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
            environment_template_id=getattr(body, "cloud_space_environment_template_id", None),
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _get_status_side_effect(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=None))

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc"),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_get_cloud_space.side_effect = _get_cloud_space_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_get_status.side_effect = _get_status_side_effect

    studio = Studio(name="st-new", teamspace="ts-abc", org="org-abc", create_ok=True)

    assert studio.name == "st-new"
    mock_get_cloud_space.assert_called()


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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
    autospec=True,
)
def test_studio_init_with_cloud_provider_without_cloud_account(
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test that Studio.__init__ can be called with cloud_provider without cloud_account."""
    mock_list_clusters.return_value = V1ListClustersResponse(
        [
            V1ExternalCluster(
                id="aws-public",
                spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="gcp-public",
                spec=V1ExternalClusterSpec(google_cloud_v1=V1GoogleCloudDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
        ]
    )

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        return V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )

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

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([])
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_STOPPED")
    )

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="test-studio-gcp",
        teamspace="ts-abc",
        org="org-abc",
        cloud_provider=CloudProvider.GCP,
        create_ok=True,
    )

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"
    assert studio.name == "test-studio-gcp"
    assert studio.cloud_account == "gcp-public"


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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
    autospec=True,
)
def test_studio_init_with_cloud_provider_string_without_cloud_account(
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test that Studio.__init__ can be called with cloud_provider as string without cloud_account."""
    mock_list_clusters.return_value = V1ListClustersResponse(
        [
            V1ExternalCluster(
                id="aws-public",
                spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="gcp-public",
                spec=V1ExternalClusterSpec(google_cloud_v1=V1GoogleCloudDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
        ]
    )

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        return V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )

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

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([])
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_STOPPED")
    )

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="test-studio-aws-str",
        teamspace="ts-abc",
        org="org-abc",
        cloud_provider="AWS",
        create_ok=True,
    )

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"
    assert studio.name == "test-studio-aws-str"
    assert studio.cloud_account == "aws-public"


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
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
    autospec=True,
)
def test_studio_init_with_cloud_provider_for_existing_studio(
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    """Test that cloud_provider arg doesn't break when accessing existing studio."""
    mock_list_clusters.return_value = V1ListClustersResponse(
        [
            V1ExternalCluster(
                id="aws-public",
                spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
            V1ExternalCluster(
                id="gcp-public",
                spec=V1ExternalClusterSpec(google_cloud_v1=V1GoogleCloudDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
        ]
    )

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse([])

    existing_studio = V1CloudSpace(
        name="existing-studio",
        display_name="existing-studio",
        cluster_id="aws-public",
        project_id="ts-abc",
        id="existing-studio",
    )

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([existing_studio])

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_STOPPED")
    )

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="existing-studio",
        teamspace="ts-abc",
        org="org-abc",
        cloud_provider=CloudProvider.GCP,
        create_ok=False,
    )

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"
    assert studio.name == "existing-studio"
    assert studio.cloud_account == "aws-public"
