from unittest.mock import patch

import pytest

from lightning_sdk.api.gpu_telemetry_api import GpuTelemetryApi


@patch("lightning_sdk.api.gpu_telemetry_api.LightningClient")
def test_gpu_telemetry_api_forwards_only_set_filters(mock_client):
    expected = object()
    mock_client.return_value.gpu_telemetry_service_list_gpu_telemetry.return_value = expected

    response = GpuTelemetryApi().list_gpu_telemetry(
        org_id="org-1",
        source_type="bm_os_agent",
        node="g068",
        page_size=25,
    )

    assert response == expected
    mock_client.return_value.gpu_telemetry_service_list_gpu_telemetry.assert_called_once_with(
        org_id="org-1",
        source_type="bm_os_agent",
        node="g068",
        page_size=25,
    )


@patch("lightning_sdk.api.gpu_telemetry_api.LightningClient")
def test_gpu_telemetry_api_forwards_all_filters(mock_client):
    expected = object()
    mock_client.return_value.gpu_telemetry_service_list_gpu_telemetry.return_value = expected

    response = GpuTelemetryApi().list_gpu_telemetry(
        org_id="org-1",
        source_type="vm_guest",
        dc="dfw1",
        cluster="lai-vms",
        node="g110",
        page_size=50,
        page_token="next",
    )

    assert response == expected
    mock_client.return_value.gpu_telemetry_service_list_gpu_telemetry.assert_called_once_with(
        org_id="org-1",
        source_type="vm_guest",
        dc="dfw1",
        cluster="lai-vms",
        node="g110",
        page_size=50,
        page_token="next",
    )


@patch("lightning_sdk.api.gpu_telemetry_api.LightningClient")
def test_gpu_telemetry_api_raises_clear_error_before_generated_client_is_vendored(mock_client):
    mock_client.return_value = object()

    with pytest.raises(RuntimeError, match="generated Grid GPU telemetry client is vendored"):
        GpuTelemetryApi().list_gpu_telemetry(org_id="org-1")
