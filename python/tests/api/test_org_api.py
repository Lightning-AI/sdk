from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.lightning_cloud.openapi import V1Organization


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_api(internal_get_org_api_mocker):
    org_api = OrgApi()

    org = org_api.get_org("org-abc")
    assert isinstance(org, V1Organization)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_api_valueerror(internal_get_org_api_mocker):
    org_api = OrgApi()

    with pytest.raises(ValueError, match="Org xyz does not exist"):
        org_api.get_org("xyz")


@mock.patch("lightning_sdk.api.utils.LightningClient")
def test_create_teamspace(mock_client):
    org_api = OrgApi()

    org_api.create_teamspace("my-teamspace", "org-123")

    mock_client().projects_service_create_project.assert_called_once()
    call_args = mock_client().projects_service_create_project.call_args
    assert call_args[1]["body"].name == "my-teamspace"
    assert call_args[1]["body"].display_name == "my-teamspace"
    assert call_args[1]["body"].organization_id == "org-123"


# ---- get_monthly_summary: time-filter validation --------------------------


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_range_forwards_bounds(mock_client):
    org_api = OrgApi()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)

    org_api.get_monthly_summary("org-123", range_start=start, range_end=end)

    call_args = mock_client().billing_service_get_monthly_summary.call_args[1]
    assert call_args["org_id"] == "org-123"
    assert call_args["time_filter_range_filter_range_start"] == start
    assert call_args["time_filter_range_filter_range_end"] == end


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_pivot_forwards_bounds(mock_client):
    org_api = OrgApi()
    pivot = datetime(2026, 1, 1, tzinfo=timezone.utc)

    org_api.get_monthly_summary("org-123", pivot=pivot, pivot_direction="BEFORE")

    call_args = mock_client().billing_service_get_monthly_summary.call_args[1]
    assert call_args["time_filter_pivot_filter_pivot"] == pivot
    assert call_args["time_filter_pivot_filter_pivot_direction"] == "BEFORE"


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_requires_exactly_one_filter(mock_client):
    org_api = OrgApi()

    # neither
    with pytest.raises(ValueError, match="exactly one"):
        org_api.get_monthly_summary("org-123")

    # both
    with pytest.raises(ValueError, match="exactly one"):
        org_api.get_monthly_summary(
            "org-123",
            range_start=datetime(2026, 1, 1),
            range_end=datetime(2026, 2, 1),
            pivot=datetime(2026, 1, 1),
            pivot_direction="BEFORE",
        )

    # partial range is treated as "no valid filter"
    with pytest.raises(ValueError, match="exactly one"):
        org_api.get_monthly_summary("org-123", range_start=datetime(2026, 1, 1))

    # partial pivot is treated as "no valid filter"
    with pytest.raises(ValueError, match="exactly one"):
        org_api.get_monthly_summary("org-123", pivot=datetime(2026, 1, 1))

    mock_client().billing_service_get_monthly_summary.assert_not_called()


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_rejects_reversed_range(mock_client):
    org_api = OrgApi()

    with pytest.raises(ValueError, match="range_start must not be after range_end"):
        org_api.get_monthly_summary(
            "org-123",
            range_start=datetime(2026, 2, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    mock_client().billing_service_get_monthly_summary.assert_not_called()


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_allows_equal_range_bounds(mock_client):
    org_api = OrgApi()
    same = datetime(2026, 1, 1, tzinfo=timezone.utc)

    org_api.get_monthly_summary("org-123", range_start=same, range_end=same)

    mock_client().billing_service_get_monthly_summary.assert_called_once()


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_rejects_bad_pivot_direction(mock_client):
    org_api = OrgApi()

    with pytest.raises(ValueError, match='"BEFORE" or "AFTER"'):
        org_api.get_monthly_summary(
            "org-123", pivot=datetime(2026, 1, 1), pivot_direction="SIDEWAYS"
        )

    mock_client().billing_service_get_monthly_summary.assert_not_called()


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_rejects_future_after_pivot(mock_client):
    org_api = OrgApi()
    future = datetime.now(timezone.utc) + timedelta(days=1)

    with pytest.raises(ValueError, match="must not be in the future"):
        org_api.get_monthly_summary("org-123", pivot=future, pivot_direction="AFTER")

    mock_client().billing_service_get_monthly_summary.assert_not_called()


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_allows_future_before_pivot(mock_client):
    """A future pivot is only rejected for AFTER; BEFORE may legitimately be in the future."""
    org_api = OrgApi()
    future = datetime.now(timezone.utc) + timedelta(days=1)

    org_api.get_monthly_summary("org-123", pivot=future, pivot_direction="BEFORE")

    mock_client().billing_service_get_monthly_summary.assert_called_once()


@mock.patch("lightning_sdk.api.org_api.LightningClient")
def test_monthly_summary_future_after_pivot_naive(mock_client):
    """Future check also works for naive datetimes (no tzinfo)."""
    org_api = OrgApi()
    future = datetime.now() + timedelta(days=1)

    with pytest.raises(ValueError, match="must not be in the future"):
        org_api.get_monthly_summary("org-123", pivot=future, pivot_direction="AFTER")
