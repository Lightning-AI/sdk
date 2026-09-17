import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from lightning_sdk.api.billing_api import (
    ActivityFileFormat,
    BillingActivity,
    BillingActivityFilterValues,
    BillingApi,
    BillingDailyUsage,
    BillingNamedFilterValue,
    BillingResourceUsage,
    _build_activity_query_params,
)

# ---- dataclasses: _from_api ------------------------------------------------


def test_billing_resource_usage_from_api():
    usage = BillingResourceUsage._from_api(
        {
            "id": "res-1",
            "user_id": "user-1",
            "project_id": "proj-1",
            "cluster_id": "cluster-1",
            "resource_type": "Studio",
            "resource_name": "my-studio",
            "created_at": "2026-01-01T00:00:00Z",
            "deleted_at": None,
            "billed_time_seconds": "120",
            "cost": 1.5,
            "saved_cost": 0.5,
            "bucket_start": "2026-01-01T00:00:00Z",
        }
    )

    assert usage.id == "res-1"
    assert usage.user_id == "user-1"
    assert usage.project_id == "proj-1"
    assert usage.cluster_id == "cluster-1"
    assert usage.resource_type == "Studio"
    assert usage.resource_name == "my-studio"
    assert usage.created_at == "2026-01-01T00:00:00Z"
    assert usage.deleted_at is None
    assert usage.billed_time_seconds == 120
    assert isinstance(usage.billed_time_seconds, int)
    assert usage.cost == 1.5
    assert usage.saved_cost == 0.5
    assert usage.bucket_start == "2026-01-01T00:00:00Z"


def test_billing_resource_usage_from_api_missing_billed_time():
    usage = BillingResourceUsage._from_api({"id": "res-1"})

    assert usage.billed_time_seconds is None


def test_billing_resource_usage_from_api_defaults():
    usage = BillingResourceUsage._from_api({})

    assert usage == BillingResourceUsage()


def test_billing_daily_usage_from_api():
    daily = BillingDailyUsage._from_api(
        {
            "day": "2026-01-01",
            "total_cost": 10.0,
            "total_saved_cost": 2.0,
            "total_prompt_tokens": "100",
            "total_completion_tokens": "200",
            "total_num_messages": "5",
        }
    )

    assert daily.day == "2026-01-01"
    assert daily.total_cost == 10.0
    assert daily.total_saved_cost == 2.0
    assert daily.total_prompt_tokens == 100
    assert daily.total_completion_tokens == 200
    assert daily.total_num_messages == 5


def test_billing_daily_usage_from_api_missing_counts_default_to_zero():
    daily = BillingDailyUsage._from_api({"day": "2026-01-01"})

    assert daily.total_prompt_tokens == 0
    assert daily.total_completion_tokens == 0
    assert daily.total_num_messages == 0


def test_billing_named_filter_value_from_api():
    value = BillingNamedFilterValue._from_api({"id": "res-1", "name": "my-resource"})

    assert value.id == "res-1"
    assert value.name == "my-resource"


def test_billing_activity_from_api():
    activity = BillingActivity._from_api(
        {
            "total_cost": 5.0,
            "total_saved_cost": 1.0,
            "usage": [{"id": "res-1"}],
            "daily_usage": [{"day": "2026-01-01"}],
            "has_more": True,
            "search_after": "2026-01-01T00:00:00Z",
            "search_after_resource_id": "res-1",
            "search_after_resource_type": "Studio",
        }
    )

    assert activity.total_cost == 5.0
    assert activity.total_saved_cost == 1.0
    assert len(activity.usage) == 1
    assert isinstance(activity.usage[0], BillingResourceUsage)
    assert activity.usage[0].id == "res-1"
    assert len(activity.daily_usage) == 1
    assert isinstance(activity.daily_usage[0], BillingDailyUsage)
    assert activity.has_more is True
    assert activity.search_after == "2026-01-01T00:00:00Z"
    assert activity.search_after_resource_id == "res-1"
    assert activity.search_after_resource_type == "Studio"


def test_billing_activity_from_api_missing_lists_default_to_empty():
    activity = BillingActivity._from_api({})

    assert activity.usage == []
    assert activity.daily_usage == []
    assert activity.has_more is False


def test_billing_activity_filter_values_from_api():
    filter_values = BillingActivityFilterValues._from_api(
        {
            "project_ids": ["proj-1", "proj-2"],
            "resource_ids": [{"id": "res-1", "name": "my-resource"}],
            "resource_ids_truncated": True,
            "resource_types": ["Studio", "Job"],
            "user_ids": ["user-1"],
        }
    )

    assert filter_values.project_ids == ["proj-1", "proj-2"]
    assert len(filter_values.resource_ids) == 1
    assert isinstance(filter_values.resource_ids[0], BillingNamedFilterValue)
    assert filter_values.resource_ids[0].id == "res-1"
    assert filter_values.resource_ids_truncated is True
    assert filter_values.resource_types == ["Studio", "Job"]
    assert filter_values.user_ids == ["user-1"]


def test_billing_activity_filter_values_from_api_missing_lists_default_to_empty():
    filter_values = BillingActivityFilterValues._from_api({})

    assert filter_values.project_ids == []
    assert filter_values.resource_ids == []
    assert filter_values.resource_ids_truncated is False
    assert filter_values.resource_types == []
    assert filter_values.user_ids == []


# ---- _build_activity_query_params ------------------------------------------


def test_build_activity_query_params_minimal():
    params = _build_activity_query_params(org_id="org-1")

    assert params == {"orgId": "org-1"}


def test_build_activity_query_params_full():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    search_after = datetime(2026, 1, 15, tzinfo=timezone.utc)

    params = _build_activity_query_params(
        org_id="org-1",
        project_ids=["proj-1"],
        resource_types=["Studio"],
        resource_ids=["res-1"],
        user_ids=["user-1"],
        start=start,
        end=end,
        limit=10,
        search_after=search_after,
        search_after_resource_id="res-1",
        search_after_resource_type="Studio",
    )

    assert params == {
        "orgId": "org-1",
        "projectIds": ["proj-1"],
        "resourceTypes": ["Studio"],
        "resourceIds": ["res-1"],
        "userIds": ["user-1"],
        "from": start.isoformat(),
        "to": end.isoformat(),
        "limit": 10,
        "searchAfter": search_after.isoformat(),
        "searchAfterResourceId": "res-1",
        "searchAfterResourceType": "Studio",
    }


# ---- BillingApi.get_activity ------------------------------------------------


@mock.patch("lightning_sdk.api.utils.LightningClient")
def test_get_activity_minimal(mock_client):
    mock_client().billing_service_get_usage_report_v2.return_value.to_dict.return_value = {}

    billing_api = BillingApi()
    result = billing_api.get_activity(org_id="org-1")

    assert isinstance(result, BillingActivity)
    call_kwargs = mock_client().billing_service_get_usage_report_v2.call_args[1]
    assert call_kwargs == {"org_id": "org-1"}


@mock.patch("lightning_sdk.api.utils.LightningClient")
def test_get_activity_forwards_all_kwargs(mock_client):
    mock_client().billing_service_get_usage_report_v2.return_value.to_dict.return_value = {}
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    search_after = datetime(2026, 1, 15, tzinfo=timezone.utc)

    billing_api = BillingApi()
    billing_api.get_activity(
        org_id="org-1",
        project_ids=["proj-1"],
        resource_types=["Studio"],
        resource_ids=["res-1"],
        user_ids=["user-1"],
        start=start,
        end=end,
        limit=10,
        search_after=search_after,
        search_after_resource_id="res-1",
        search_after_resource_type="Studio",
    )

    call_kwargs = mock_client().billing_service_get_usage_report_v2.call_args[1]
    assert call_kwargs == {
        "org_id": "org-1",
        "project_ids": ["proj-1"],
        "resource_types": ["Studio"],
        "resource_ids": ["res-1"],
        "user_ids": ["user-1"],
        "_from": start,
        "to": end,
        "limit": 10,
        "search_after": search_after,
        "search_after_resource_id": "res-1",
        "search_after_resource_type": "Studio",
    }


# ---- BillingApi.get_activity_filter_values -----------------------------------


@mock.patch("lightning_sdk.api.utils.LightningClient")
def test_get_activity_filter_values_minimal(mock_client):
    mock_client().billing_service_get_activity_filter_values.return_value.to_dict.return_value = {}

    billing_api = BillingApi()
    result = billing_api.get_activity_filter_values(org_id="org-1")

    assert isinstance(result, BillingActivityFilterValues)
    call_kwargs = mock_client().billing_service_get_activity_filter_values.call_args[1]
    assert call_kwargs == {"org_id": "org-1"}


@mock.patch("lightning_sdk.api.utils.LightningClient")
def test_get_activity_filter_values_with_project_id(mock_client):
    mock_client().billing_service_get_activity_filter_values.return_value.to_dict.return_value = {}

    billing_api = BillingApi()
    billing_api.get_activity_filter_values(org_id="org-1", project_id="proj-1")

    call_kwargs = mock_client().billing_service_get_activity_filter_values.call_args[1]
    assert call_kwargs == {"org_id": "org-1", "project_id": "proj-1"}


# ---- CSV downloads ----------------------------------------------------------


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.api.billing_api._authenticate_and_get_auth_headers",
    return_value={"Authorization": "Bearer test-token"},
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_session_activity_csv(mock_authenticate, mock_requests_get, tmp_path):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "4"}
    mock_response.iter_content = mock.Mock(return_value=[b"data"])
    mock_requests_get.return_value = mock_response

    billing_api = BillingApi()
    target_path = tmp_path / "detailed.csv"

    result = billing_api.get_session_activity(
        org_id="org-1", format=ActivityFileFormat.CSV, target_path=str(target_path)
    )

    assert result is None
    mock_authenticate.assert_called_once_with()
    mock_requests_get.assert_called_once()
    call_args = mock_requests_get.call_args
    assert call_args[0][0].endswith("/v1/billing/usage-report/download/detailed")
    assert call_args[1]["params"] == {"orgId": "org-1"}
    assert call_args[1]["headers"] == {"Authorization": "Bearer test-token"}


def test_get_session_activity_csv_requires_target_path():
    billing_api = BillingApi()

    with pytest.raises(ValueError, match="target_path"):
        billing_api.get_session_activity(org_id="org-1", format=ActivityFileFormat.CSV)


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.api.billing_api._authenticate_and_get_auth_headers",
    return_value={"Authorization": "Bearer test-token"},
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_session_activity_json_default_format(mock_authenticate, mock_requests_get, tmp_path):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "21"}
    mock_response.iter_content = mock.Mock(return_value=[b"id,name\nres-1,studio\n"])
    mock_requests_get.return_value = mock_response

    billing_api = BillingApi()
    target_path = tmp_path / "detailed.json"

    result = billing_api.get_session_activity(org_id="org-1", target_path=str(target_path))

    assert result == [{"id": "res-1", "name": "studio"}]
    assert json.loads(Path(target_path).read_text()) == [{"id": "res-1", "name": "studio"}]
    call_args = mock_requests_get.call_args
    assert call_args[0][0].endswith("/v1/billing/usage-report/download/detailed")


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.api.billing_api._authenticate_and_get_auth_headers",
    return_value={"Authorization": "Bearer test-token"},
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_resource_activity_csv(mock_authenticate, mock_requests_get, tmp_path):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "4"}
    mock_response.iter_content = mock.Mock(return_value=[b"data"])
    mock_requests_get.return_value = mock_response

    billing_api = BillingApi()
    target_path = tmp_path / "summary.csv"

    result = billing_api.get_resource_activity(
        org_id="org-1",
        format=ActivityFileFormat.CSV,
        target_path=str(target_path),
        project_ids=["proj-1"],
        limit=5,
    )

    assert result is None
    mock_authenticate.assert_called_once_with()
    call_args = mock_requests_get.call_args
    assert call_args[0][0].endswith("/v1/billing/usage-report/download/summary")
    assert call_args[1]["params"] == {"orgId": "org-1", "projectIds": ["proj-1"], "limit": 5}


def test_get_resource_activity_csv_requires_target_path():
    billing_api = BillingApi()

    with pytest.raises(ValueError, match="target_path"):
        billing_api.get_resource_activity(org_id="org-1", format=ActivityFileFormat.CSV)


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.api.billing_api._authenticate_and_get_auth_headers",
    return_value={"Authorization": "Bearer test-token"},
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_resource_activity_json_default_format(mock_authenticate, mock_requests_get, tmp_path):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "21"}
    mock_response.iter_content = mock.Mock(return_value=[b"id,name\nres-1,studio\n"])
    mock_requests_get.return_value = mock_response

    billing_api = BillingApi()
    target_path = tmp_path / "summary.json"

    result = billing_api.get_resource_activity(org_id="org-1", target_path=str(target_path))

    assert result == [{"id": "res-1", "name": "studio"}]
    assert json.loads(Path(target_path).read_text()) == [{"id": "res-1", "name": "studio"}]
    call_args = mock_requests_get.call_args
    assert call_args[0][0].endswith("/v1/billing/usage-report/download/summary")
