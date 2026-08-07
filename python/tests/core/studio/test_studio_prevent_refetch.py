"""Regression tests: under ``prevent_refetch_studio``, ``status``/``machine`` must be served from the
already-fetched ``code_status`` instead of issuing a live per-Studio API call.
"""

from unittest import mock

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    V1AWSDirectV1,
    V1CloudProvider,
    V1CloudSpace,
    V1ClusterAccelerator,
    V1ClusterType,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1GetCloudSpaceInstanceStatusResponse,
    V1ListCloudSpacesResponse,
    V1ListClustersResponse,
    V1ListDefaultClusterAcceleratorsResponse,
    V1ListProjectClustersResponse,
    V1Organization,
    V1Project,
    V1ProjectSettings,
    V1Resources,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import prevent_refetch_studio


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi."
    "cluster_service_list_default_cluster_accelerators",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi."
    "cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi."
    "cloud_space_service_get_cloud_space_instance_config",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi."
    "cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi."
    "cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_status_and_machine_use_cached_code_status_when_refetch_prevented(
    mock_get_teamspace,
    mock_get_org,
    mock_list_cloudspaces,
    mock_get_status,
    mock_get_config,
    mock_list_project_clusters,
    mock_list_clusters,
    mock_list_accelerators,
):
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc"),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )

    cloudspace = V1CloudSpace(
        name="st-abc",
        display_name="st-abc",
        cluster_id="c-abc",
        project_id="ts-abc",
        id="st-abc",
        code_status=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
                compute_config=V1UserRequestedComputeConfig(name="cpu-4"),
            )
        ),
    )
    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([cloudspace])

    # Raise instead of returning a plausible value, so a regression fails the test rather than just
    # adding invisible latency on real teamspaces.
    mock_get_status.side_effect = AssertionError("must not refetch studio status when refetch is prevented")
    mock_get_config.side_effect = AssertionError("must not refetch instance config when refetch is prevented")

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=[])
    mock_list_clusters.return_value = V1ListClustersResponse(
        clusters=[
            V1ExternalCluster(
                id="c-abc",
                spec=V1ExternalClusterSpec(
                    driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
                ),
            )
        ]
    )
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                instance_id="cpu-4",
                slug_multi_cloud="cpu-4",
                enabled=True,
                resources=V1Resources(cpu=4),
                family="CPU",
                accelerator_type="CPU",
            )
        ]
    )

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc", create_ok=False)

    with prevent_refetch_studio(studio):
        assert studio.status == Status.Running
        assert studio.machine == Machine.CPU

    mock_get_status.assert_not_called()
    mock_get_config.assert_not_called()


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi."
    "cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi."
    "cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_status_still_refetches_when_not_prevented(
    mock_get_teamspace,
    mock_get_org,
    mock_list_cloudspaces,
    mock_get_status,
):
    """Baseline: outside of prevent_refetch_studio, status must stay live (no caching regression)."""
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc"),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )

    cloudspace = V1CloudSpace(
        name="st-abc",
        display_name="st-abc",
        cluster_id="c-abc",
        project_id="ts-abc",
        id="st-abc",
        # stale/absent code_status on the listed object -- status must not be read from this.
        code_status=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_STOPPED")
        ),
    )
    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([cloudspace])
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
    )

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc", create_ok=False)

    assert studio.status == Status.Running
    mock_get_status.assert_called_once()
