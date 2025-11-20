from datetime import datetime
from unittest import mock

import pandas as pd

from lightning_sdk.api.billing_api import BillingApi
from lightning_sdk.lightning_cloud.openapi.models import V1ClusterMetrics, V1ListClusterMetricsResponse

mock_cluster = [
    {"timestamp": datetime(2025, 11, 19, 12), "num_allocated_gpus": 6},
    {"timestamp": datetime(2025, 11, 19, 13), "num_allocated_gpus": 4},
]


def test_get_k8s_usage_with_empty_metrics():
    billing_api = BillingApi()
    get_k8s_mock = mock.Mock(return_value=V1ListClusterMetricsResponse(cluster_metrics=[]))

    billing_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = billing_api.get_k8s_usage("test")

    assert isinstance(result, pd.DataFrame)
    assert result.shape[0] == 0

    get_k8s_mock.assert_called_once_with("test")


def test_get_k8s_usage_metrics_with_no_range():
    billing_api = BillingApi()
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**data) for data in mock_cluster])
    )

    billing_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = billing_api.get_k8s_usage("test")

    assert isinstance(result, pd.DataFrame)
    assert result.shape[0] == 2
    assert result.iloc[0]["num_allocated_gpus"] == 6

    get_k8s_mock.assert_called_once_with("test")


def test_gets_calculates_metrics_with_start_and_end_dates():
    billing_api = BillingApi()
    start_date = datetime(2025, 11, 19, 11, 30)
    end_date = datetime(2025, 11, 19, 14, 0, 0)
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**data) for data in mock_cluster])
    )
    billing_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = billing_api.get_k8s_usage("user-abc", start_date=start_date, end_date=end_date)
    assert isinstance(result, pd.DataFrame)
    assert result.shape[0] == 2
    assert result.iloc[0]["num_allocated_gpus"] == 6.0
    assert result.iloc[1]["num_allocated_gpus"] == 4.0


def test_gets_calculates_metrics_with_only_start_date():
    billing_api = BillingApi()
    date = datetime(2025, 11, 19, 12, 30)
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**mock_cluster[1])])
    )
    billing_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = billing_api.get_k8s_usage("user-abc", start_date=date)
    assert result.shape[0] == 1
    assert result.iloc[0]["num_allocated_gpus"] == 4.0
    get_k8s_mock.assert_called_once_with("user-abc", start_date=date)


def test_gets_calculates_metrics_with_only_end_date():
    billing_api = BillingApi()
    date = datetime(2025, 11, 19, 12, 30)
    get_k8s_mock = mock.Mock(
        return_value=V1ListClusterMetricsResponse(cluster_metrics=[V1ClusterMetrics(**mock_cluster[0])])
    )
    billing_api._client.k8_s_cluster_service_list_cluster_metrics = get_k8s_mock

    result = billing_api.get_k8s_usage("user-abc", end_date=date)
    assert result.shape[0] == 1
    assert result.iloc[0]["num_allocated_gpus"] == 6.0
    get_k8s_mock.assert_called_once_with("user-abc", end_date=date)
