from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    V1AWSDirectV1,
    V1CloudSpace,
    V1CloudSpaceInstanceStartupStatus,
    V1ClusterType,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GoogleCloudDirectV1,
    V1ListCloudSpacesResponse,
    V1ListClustersResponse,
    V1ListProjectClustersResponse,
    V1Organization,
    V1Project,
    V1ProjectSettings,
)
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.studio import Studio


@pytest.fixture()
def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


@mock.patch("requests.put", autospec=True)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_switch_cloud_account(
    mock_switch_cloudspace_instance,
    mock_update_cloudspace_instance_config,
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_requests_put,
):
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

    cloudspace = V1CloudSpace(
        name="st-abc", display_name="st-abc", cluster_id="aws-public", project_id="ts-abc", id="st-abc"
    )

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([cloudspace])

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
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

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    assert studio.cloud_account == "aws-public"

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
        ),
    )

    studio.switch_machine(Machine.T4, cloud_provider=CloudProvider.GCP)

    assert studio.cloud_account == "gcp-public"


@mock.patch("requests.put", autospec=True)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_studio_switch_cloud_account_not_global(
    mock_switch_cloudspace_instance,
    mock_update_cloudspace_instance_config,
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_requests_put,
):
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

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(
        [
            V1ExternalCluster(
                id="aws-private",
                spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.BYOC),
            ),
        ]
    )

    cloudspace = V1CloudSpace(
        name="st-abc", display_name="st-abc", cluster_id="aws-private", project_id="ts-abc", id="st-abc"
    )

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([cloudspace])

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
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

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    assert studio.cloud_account == "aws-private"

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
        ),
    )

    studio.switch_machine(Machine.T4, cloud_provider=CloudProvider.GCP)

    assert studio.cloud_account == "aws-private"
