from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.lightning_cloud.openapi import V1CloudProvider, V1ExternalCluster, V1ExternalClusterSpec
from lightning_sdk.lightning_cloud.openapi.models.v1_list_cluster_accelerators_response import (
    V1ListClusterAcceleratorsResponse,
)
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
    mock_client.return_value.cluster_service_list_cluster_accelerators.return_value = accelerator_response
    cloud_account_api = CloudAccountApi()
    res = cloud_account_api.list_cloud_account_accelerators("test-cluster", "lightning-ai")
    assert res == accelerator_response


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
def api():
    return CloudAccountApi()


def test_returns_cloud_account_if_given(api):
    result = api.resolve_cloud_account(
        teamspace_id="ts", cloud_account="acc-1", cloud_provider=None, default_cloud_account=None
    )
    assert result == "acc-1"


def test_returns_cloud_account_if_given_and_matching_provider(api):
    cluster = make_cluster("acc-1", driver=V1CloudProvider.GCP)
    api.get_cloud_account_non_org = MagicMock(return_value=cluster)
    api._get_cloud_account_provider = MagicMock(return_value=CloudProvider.GCP)

    result = api.resolve_cloud_account(
        teamspace_id="ts", cloud_account="acc-1", cloud_provider=CloudProvider.GCP, default_cloud_account=None
    )
    assert result == "acc-1"


def test_raises_if_mismatching_provider(api):
    cluster = make_cluster("acc-1", driver=V1CloudProvider.GCP)
    api.get_cloud_account_non_org = MagicMock(return_value=cluster)
    api._get_cloud_account_provider = MagicMock(return_value=CloudProvider.GCP)

    with pytest.raises(RuntimeError, match="don't match"):
        api.resolve_cloud_account(
            teamspace_id="ts", cloud_account="acc-1", cloud_provider=CloudProvider.AWS, default_cloud_account=None
        )


def test_returns_mapped_account_if_only_provider_given(api):
    api.get_cloud_account_provider_mapping = MagicMock(return_value={CloudProvider.GCP: "acc-gcp"})

    result = api.resolve_cloud_account(
        teamspace_id="ts", cloud_account=None, cloud_provider=CloudProvider.GCP, default_cloud_account=None
    )
    assert result == "acc-gcp"


def test_returns_default_if_no_account_and_no_matching_provider(api):
    api.get_cloud_account_provider_mapping = MagicMock(return_value={})
    result = api.resolve_cloud_account(
        teamspace_id="ts", cloud_account=None, cloud_provider=None, default_cloud_account="acc-default"
    )
    assert result == "acc-default"


def test_returns_none_if_nothing_matches(api):
    api.get_cloud_account_provider_mapping = MagicMock(return_value={})
    result = api.resolve_cloud_account(
        teamspace_id="ts", cloud_account=None, cloud_provider=None, default_cloud_account=None
    )
    assert result is None
