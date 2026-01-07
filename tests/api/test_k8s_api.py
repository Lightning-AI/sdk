from datetime import datetime
from unittest import mock

import pytest

from lightning_sdk.api.k8s_api import K8sClusterApi, K8sClusterApiError
from lightning_sdk.lightning_cloud.openapi.models import V1ClusterMetrics, V1ListClusterMetricsResponse

mock_cluster = [
    {"timestamp": datetime(2025, 11, 19, 12), "num_allocated_gpus": 6, "num_requested_gpus": 6, "num_gpus": 8},
    {"timestamp": datetime(2025, 11, 19, 13), "num_allocated_gpus": 4, "num_requested_gpus": 4, "num_gpus": 8},
]


def test_get_billing_usage_with_empty_metrics():
    k8s_api = K8sClusterApi("test")
    get_k8s_mock = mock.Mock(return_value=V1ListClusterMetricsResponse(cluster_metrics=[]))

    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = k8s_api.get_billing_usage()

    assert isinstance(result, list)
    assert len(result) == 0

    get_k8s_mock.assert_called_once_with("test")


def test_get_billing_usage_metrics_with_no_range():
    k8s_api = K8sClusterApi("test")
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**data) for data in mock_cluster])
    )

    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = k8s_api.get_billing_usage()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["num_allocated_gpus"] == 6

    get_k8s_mock.assert_called_once_with("test")


def test_gets_calculates_metrics_with_start_and_end_dates():
    k8s_api = K8sClusterApi("user-abc")
    start_date = datetime(2025, 11, 19, 11, 30)
    end_date = datetime(2025, 11, 19, 14, 0, 0)
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**data) for data in mock_cluster])
    )
    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = k8s_api.get_billing_usage(start_date=start_date, end_date=end_date)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["num_allocated_gpus"] == 6.0
    assert result[1]["num_allocated_gpus"] == 4.0


def test_gets_calculates_metrics_with_only_start_date():
    k8s_api = K8sClusterApi("user-abc")
    date = datetime(2025, 11, 19, 12, 30)
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**mock_cluster[1])])
    )
    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = k8s_api.get_billing_usage(start_date=date)
    assert len(result) == 1
    assert result[0]["num_allocated_gpus"] == 4.0
    get_k8s_mock.assert_called_once_with("user-abc", start_date=date)


def test_gets_calculates_metrics_with_only_end_date():
    k8s_api = K8sClusterApi("user-abc")
    date = datetime(2025, 11, 19, 12, 30)
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**mock_cluster[0])])
    )
    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = k8s_api.get_billing_usage(end_date=date)
    assert len(result) == 1
    assert result[0]["num_allocated_gpus"] == 6.0
    get_k8s_mock.assert_called_once_with("user-abc", end_date=date)


def test_gets_raises_error_with_nonexistant_cluster():
    k8s_api = K8sClusterApi("fakey-abc")
    date = datetime(2025, 11, 19, 12, 30)

    with pytest.raises(K8sClusterApiError):
        k8s_api.get_billing_usage(end=date)


def test_get_billing_usage_metrics_print_to_stdout():
    k8s_api = K8sClusterApi("test")
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**data) for data in mock_cluster])
    )

    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    with mock.patch("rich.console.Console.print") as mock_console_print:
        k8s_api.get_billing_usage(print_data=True)
        assert mock_console_print.call_count == 1  # Rich table print

    get_k8s_mock.assert_called_once_with("test")


def test_get_billing_usage_with_dates_get_folded_into_same_hour():
    k8s_api = K8sClusterApi("test")
    test_cluster = [
        mock_cluster[0],
        mock_cluster[1],
        {
            "timestamp": datetime(2025, 11, 19, 12, 30),
            "num_allocated_gpus": 10,
            "num_requested_gpus": 10,
            "num_gpus": 8,
        },
        {
            "timestamp": datetime(2025, 11, 19, 13, 45),
            "num_allocated_gpus": 8,
            "num_requested_gpus": 8,
            "num_gpus": 12,
        },
    ]
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**data) for data in test_cluster])
    )

    k8s_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = k8s_api.get_billing_usage(print_data=True)

    assert len(result) == 2
    assert result[0]["hour"] == datetime(2025, 11, 19, 12, 0, 0)
    assert result[1]["hour"] == datetime(2025, 11, 19, 13, 0, 0)
    # The average between 6 and 10 is 8.0 meaning we properly folded the data
    assert result[0]["num_allocated_gpus"] == 8.0
    assert result[1]["num_allocated_gpus"] == 6.0
    get_k8s_mock.assert_called_once_with("test")
