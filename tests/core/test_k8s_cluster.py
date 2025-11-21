from datetime import datetime
from unittest import mock

import pandas as pd

from lightning_sdk import K8sCluster
from lightning_sdk.api.utils import to_iso_z
from lightning_sdk.k8s_cluster import K8sUsageResponse

mock_cluster = [
    {
        "timestamp": datetime(2025, 11, 19, 12),
        "num_allocated_gpus": 6,
        "billed_gpus": 6,
        "num_gpus": 8,
        "hour": datetime(2025, 11, 19, 12),
    },
    {
        "timestamp": datetime(2025, 11, 19, 13),
        "num_allocated_gpus": 4,
        "billed_gpus": 4,
        "num_gpus": 8,
        "hour": datetime(2025, 11, 19, 13),
    },
]


def test_get_billing_usage_with_empty_metrics():
    k8s_api = K8sCluster("test")
    get_billing_usage_mock = mock.Mock(return_value=pd.DataFrame.from_records([]))

    k8s_api._k8s_cluster.get_billing_usage = get_billing_usage_mock

    result = k8s_api.get_billing_usage()

    assert isinstance(result, K8sUsageResponse)
    assert result.total_usage == 0
    assert len(result.hours) == 0
    get_billing_usage_mock.assert_called_once_with(print_data=False)


def test_get_billing_usage_with_no_range():
    k8s_api = K8sCluster("test")
    get_billing_usage_mock = mock.Mock(return_value=pd.DataFrame.from_records(mock_cluster))

    k8s_api._k8s_cluster.get_billing_usage = get_billing_usage_mock

    result = k8s_api.get_billing_usage()

    assert isinstance(result, K8sUsageResponse)
    assert result.total_usage == 10.0
    assert len(result.hours) == 2
    assert result.hours[0].billed_gpus == 6
    assert result.hours[1].billed_gpus == 4
    get_billing_usage_mock.assert_called_once_with(print_data=False)


def test_get_billing_usage_with_only_start():
    k8s_api = K8sCluster("test")
    get_billing_usage_mock = mock.Mock(return_value=pd.DataFrame.from_records([mock_cluster[1]]))
    date = datetime(2025, 11, 19, 12, 30)

    k8s_api._k8s_cluster.get_billing_usage = get_billing_usage_mock

    result = k8s_api.get_billing_usage(start_date=date)

    assert isinstance(result, K8sUsageResponse)
    assert result.total_usage == 4.0
    assert len(result.hours) == 1
    assert result.hours[0].billed_gpus == 4
    assert result.hours[0].available_gpus == 8
    assert result.hours[0].time.isoformat() == "2025-11-19T13:00:00"
    get_billing_usage_mock.assert_called_once_with(print_data=False, start=to_iso_z(date))


def test_get_billing_usage_with_only_end():
    k8s_api = K8sCluster("test")
    get_billing_usage_mock = mock.Mock(return_value=pd.DataFrame.from_records([mock_cluster[0]]))
    date = datetime(2025, 11, 19, 12, 30)

    k8s_api._k8s_cluster.get_billing_usage = get_billing_usage_mock

    result = k8s_api.get_billing_usage(end_date=date)

    assert isinstance(result, K8sUsageResponse)
    assert result.total_usage == 6.0
    assert len(result.hours) == 1
    assert result.hours[0].billed_gpus == 6
    assert result.hours[0].available_gpus == 8
    assert result.hours[0].time.isoformat() == "2025-11-19T12:00:00"
    get_billing_usage_mock.assert_called_once_with(print_data=False, end=to_iso_z(date))


def test_get_billing_usage_with_date_range():
    k8s_api = K8sCluster("test")
    get_billing_usage_mock = mock.Mock(return_value=pd.DataFrame.from_records(mock_cluster))
    start_date = datetime(2025, 11, 19, 10, 30)
    end_date = datetime(2025, 11, 19, 16, 30)

    k8s_api._k8s_cluster.get_billing_usage = get_billing_usage_mock

    result = k8s_api.get_billing_usage(start_date=start_date, end_date=end_date)

    assert isinstance(result, K8sUsageResponse)
    assert result.total_usage == 10.0
    assert len(result.hours) == 2
    assert result.hours[0].billed_gpus == 6
    assert result.hours[0].available_gpus == 8
    assert result.hours[0].time.isoformat() == "2025-11-19T12:00:00"
    assert result.hours[1].billed_gpus == 4
    assert result.hours[1].available_gpus == 8
    assert result.hours[1].time.isoformat() == "2025-11-19T13:00:00"
    get_billing_usage_mock.assert_called_once_with(print_data=False, start=to_iso_z(start_date), end=to_iso_z(end_date))
