import pytest

from lightning_sdk.lightning_cloud.openapi import V1CloudProvider
from lightning_sdk.machine import CloudProvider


@pytest.mark.parametrize(
    "cloud_provider_str", ["AWS", "GCP", "LAMBDA_LABS", "DGX", "VOLTAGE_PARK", "NEBIUS", "LIGHTNING"]
)
def test_equality_cloud_provider_generated_cloud_provider_str(cloud_provider_str):
    # asserts the cloud_provider string value equality.
    # It's important for these to match since we convert the CloudProvider to string and send it to the backend then.
    assert str(getattr(CloudProvider, cloud_provider_str)) == cloud_provider_str
    assert str(getattr(V1CloudProvider, cloud_provider_str)) == cloud_provider_str
