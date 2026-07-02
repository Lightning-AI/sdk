from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.lightning_cloud.openapi import (
    V1AWSDirectV1,
    V1CloudProvider,
    V1ClusterType,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1MachineDirectV1,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_list_cluster_accelerators_response import (
    V1ListClusterAcceleratorsResponse,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_list_clusters_response import V1ListClustersResponse
from lightning_sdk.lightning_cloud.openapi.models.v1_list_project_clusters_response import V1ListProjectClustersResponse
from lightning_sdk.machine import CloudProvider


@pytest.fixture()
def accelerator_response():
    return V1ListClusterAcceleratorsResponse(
        accelerator=[
            {
                "accelerator_type": "GPU",
                "allowed_resources": [],
                "available_in_seconds": "15",
                "available_in_seconds_spot": "79",
                "available_zones": ["us-east-1", "us-east-2"],
                "byoc_only": False,
                "capacity_block_only": False,
                "capacity_block_price": 0.0,
                "capacity_blocks_available": [],
                "cluster_id": "lightning-public-prod",
                "cost": 0.68,
                "device_info": "This is a test device",
                "display_name": "T4",
                "dws_only": False,
                "enabled": True,
                "family": "T4",
                "instance_id": "g4dn.2xlarge",
                "provider": "AWS",
                "resources": {
                    "cpu": 8,
                    "cpus": "",
                    "gpu": 1,
                },
                "slug": "g4dn.2xlarge",
            }
        ],
    )


@patch("lightning_sdk.api.cloud_account_api.LightningClient")
def test_list_cloud_account_accelerators(mock_client, accelerator_response):
    # Create a mock cloud account that matches the test-cluster id
    mock_cloud_account = V1ExternalCluster(
        id="test-cluster",
        spec=V1ExternalClusterSpec(
            driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
        ),
    )

    # Mock the list_cloud_accounts method to return our test cloud account
    mock_project_response = V1ListProjectClustersResponse(clusters=[mock_cloud_account])
    mock_global_response = V1ListClustersResponse(clusters=[])
    mock_client.return_value.cluster_service_list_project_clusters.return_value = mock_project_response
    mock_client.return_value.cluster_service_list_clusters.return_value = mock_global_response

    # Mock the _list_default_cluster_accelerators method to return the accelerator response
    mock_client.return_value.cluster_service_list_default_cluster_accelerators.return_value = accelerator_response

    cloud_account_api = CloudAccountApi()
    res = cloud_account_api.list_cloud_account_accelerators("test-teamspace", "test-cluster", "test-org")
    assert res == accelerator_response
    mock_client.return_value.cluster_service_list_default_cluster_accelerators.assert_called_once_with(
        project_id="test-teamspace",
        cloud_provider=V1CloudProvider.AWS,
    )


@patch("lightning_sdk.api.cloud_account_api.LightningClient")
def test_list_default_lightning_accelerators_uses_machine_provider(mock_client, accelerator_response):
    mock_cloud_account = V1ExternalCluster(
        id="test-cluster",
        spec=V1ExternalClusterSpec(
            cluster_type=V1ClusterType.GLOBAL,
            machine_v1=V1MachineDirectV1(),
        ),
    )

    mock_client.return_value.cluster_service_list_project_clusters.return_value = V1ListProjectClustersResponse(
        clusters=[mock_cloud_account]
    )
    mock_client.return_value.cluster_service_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_client.return_value.cluster_service_list_default_cluster_accelerators.return_value = accelerator_response

    cloud_account_api = CloudAccountApi()
    res = cloud_account_api.list_cloud_account_accelerators("test-teamspace", "test-cluster", "test-org")

    assert res == accelerator_response
    mock_client.return_value.cluster_service_list_default_cluster_accelerators.assert_called_once_with(
        project_id="test-teamspace",
        cloud_provider=V1CloudProvider.MACHINE,
    )


@patch("lightning_sdk.api.cloud_account_api.LightningClient")
def test_list_cloud_accounts(mock_client):
    cloud_account_api = CloudAccountApi()
    cloud_account_api.list_cloud_accounts("test-project")

    mock_client.return_value.cluster_service_list_project_clusters.assert_called_once_with(
        project_id="test-project",
    )


def make_cluster(id_, driver=None, **kwargs):
    spec = V1ExternalClusterSpec(driver=driver, **kwargs)
    return V1ExternalCluster(id=id_, spec=spec)


@pytest.fixture()
def api(mocker):
    mocker.patch("lightning_sdk.api.cloud_account_api.LightningClient")
    return CloudAccountApi()


def test_returns_cloud_account_if_cloud_is_custom_account(api):
    result = api.resolve_cloud_account(teamspace_id="ts", cloud="acc-1", default_cloud_account=None)
    assert result == "acc-1"


@pytest.mark.parametrize("cloud", ["gcp", "GCP", CloudProvider.GCP])
def test_returns_mapped_account_if_cloud_is_provider(api, cloud):
    api.get_cloud_account_provider_mapping = MagicMock(
        return_value={CloudProvider.GCP: V1ExternalCluster(id="acc-gcp")}
    )

    result = api.resolve_cloud_account(teamspace_id="ts", cloud=cloud, default_cloud_account=None)
    assert result == "acc-gcp"


@pytest.mark.parametrize("cloud", ["lightning", CloudProvider.LIGHTNING])
def test_returns_global_lightning_account_if_cloud_is_lightning(api, cloud):
    api.get_cloud_account_provider_mapping = MagicMock(
        return_value={CloudProvider.LIGHTNING: V1ExternalCluster(id="acc-lightning")}
    )

    result = api.resolve_cloud_account(teamspace_id="ts", cloud=cloud, default_cloud_account=None)
    assert result == "acc-lightning"


def test_returns_default_if_no_account_and_no_matching_provider(api):
    api.get_cloud_account_provider_mapping = MagicMock(return_value={})
    result = api.resolve_cloud_account(teamspace_id="ts", default_cloud_account="acc-default")
    assert result == "acc-default"


def test_returns_none_if_nothing_matches(api):
    api.get_cloud_account_provider_mapping = MagicMock(return_value={})
    result = api.resolve_cloud_account(teamspace_id="ts", default_cloud_account=None)
    assert result is None


def _byoc_aws() -> V1ExternalCluster:
    return V1ExternalCluster(
        id="acc-byoc-aws",
        spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.BYOC, aws_v1=V1AWSDirectV1()),
    )


def _global_aws() -> V1ExternalCluster:
    return V1ExternalCluster(
        id="acc-global-aws",
        spec=V1ExternalClusterSpec(
            driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
        ),
    )


def test_provider_mapping_global_only_excludes_byoc(api):
    # BYOC accounts surface via the project listing, globals via the global listing.
    api._client.cluster_service_list_project_clusters.return_value = V1ListProjectClustersResponse(
        clusters=[_byoc_aws()]
    )
    api._client.cluster_service_list_clusters.return_value = V1ListClustersResponse(clusters=[_global_aws()])

    assert api.get_cloud_account_provider_mapping(teamspace_id="ts", global_only=True)[CloudProvider.AWS].id == (
        "acc-global-aws"
    )


def test_provider_mapping_includes_byoc_when_not_global_only(api):
    # Data connections still need to bind to a private/BYOC account of the right provider.
    api._client.cluster_service_list_project_clusters.return_value = V1ListProjectClustersResponse(
        clusters=[_byoc_aws()]
    )
    api._client.cluster_service_list_clusters.return_value = V1ListClustersResponse(clusters=[])

    assert api.get_cloud_account_provider_mapping(teamspace_id="ts")[CloudProvider.AWS].id == "acc-byoc-aws"


@pytest.mark.parametrize("cloud", ["aws", "AWS", CloudProvider.AWS])
def test_cloud_aws_resolves_to_global_account_over_byoc(api, cloud):
    """--cloud aws must select the GLOBAL AWS account even when a BYOC AWS account also exists."""
    api._client.cluster_service_list_project_clusters.return_value = V1ListProjectClustersResponse(
        clusters=[_byoc_aws()]
    )
    api._client.cluster_service_list_clusters.return_value = V1ListClustersResponse(clusters=[_global_aws()])

    result = api.resolve_cloud_account(teamspace_id="ts", cloud=cloud, default_cloud_account="acc-default")
    assert result == "acc-global-aws"


def test_cloud_aws_falls_back_to_default_when_only_byoc_account(api):
    """A BYOC-only AWS teamspace must not be matched by --cloud aws; fall through to the default."""
    api._client.cluster_service_list_project_clusters.return_value = V1ListProjectClustersResponse(
        clusters=[_byoc_aws()]
    )
    api._client.cluster_service_list_clusters.return_value = V1ListClustersResponse(clusters=[])

    result = api.resolve_cloud_account(teamspace_id="ts", cloud="aws", default_cloud_account="acc-default")
    assert result == "acc-default"


def test_provider_mapping_empty_when_teamspace_has_no_accounts(api):
    api._client.cluster_service_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=[])
    api._client.cluster_service_list_clusters.return_value = V1ListClustersResponse(clusters=[])

    assert api.get_cloud_account_provider_mapping(teamspace_id="ts") == {}

    result = api.resolve_cloud_account(teamspace_id="ts", cloud="aws", default_cloud_account="acc-default")
    assert result == "acc-default"


@pytest.mark.parametrize(
    ("cloud_provider", "v1_cloud_provider"),
    [
        (CloudProvider.AWS, V1CloudProvider.AWS),
        (CloudProvider.GCP, V1CloudProvider.GCP),
        (CloudProvider.DGX, V1CloudProvider.DGX),
        (CloudProvider.LAMBDA_LABS, V1CloudProvider.LAMBDA_LABS),
        (CloudProvider.NEBIUS, V1CloudProvider.NEBIUS),
        (CloudProvider.VOLTAGE_PARK, V1CloudProvider.VOLTAGE_PARK),
        (CloudProvider.LIGHTNING_AGGREGATE, V1CloudProvider.LIGHTNING_AGGREGATE),
        (CloudProvider.LIGHTNING, V1CloudProvider.MACHINE),
        ("lightning", V1CloudProvider.MACHINE),
    ],
)
def test_cloud_provider_to_v1_cloud_provider(api, cloud_provider, v1_cloud_provider):
    assert api.cloud_provider_to_v1_cloud_provider(cloud_provider) == v1_cloud_provider


@pytest.mark.parametrize(
    ("cluster_spec", "expected_provider"),
    [
        (V1ExternalClusterSpec(driver=V1CloudProvider.LIGHTNING), CloudProvider.LIGHTNING_AGGREGATE),
        (V1ExternalClusterSpec(machine_v1=V1MachineDirectV1()), CloudProvider.LIGHTNING),
    ],
)
def test_get_cloud_account_provider_distinguishes_lightning_providers(api, cluster_spec, expected_provider):
    cluster = V1ExternalCluster(id="acc-lightning", spec=cluster_spec)

    assert api._get_cloud_account_provider(cluster) == expected_provider
