from unittest.mock import patch

import pytest

from lightning_sdk.api.cluster_api import ClusterApi
from lightning_sdk.lightning_cloud.openapi.models.v1_list_cluster_accelerators_response import (
    V1ListClusterAcceleratorsResponse,
)


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


@patch("lightning_sdk.api.cluster_api.LightningClient")
def test_list_cluster_accelerators(mock_client, accelerator_response):
    mock_client.return_value.cluster_service_list_cluster_accelerators.return_value = accelerator_response
    cluster_api = ClusterApi()
    res = cluster_api.list_cluster_accelerators("test-cluster", "lightning-ai")
    assert res == accelerator_response


@patch("lightning_sdk.api.cluster_api.LightningClient")
def test_list_clusters(mock_client):
    cluster_api = ClusterApi()
    cluster_api.list_clusters("test-project")

    mock_client.return_value.cluster_service_list_project_clusters.assert_called_once_with(
        project_id="test-project",
    )
