from unittest import mock

import pytest

from lightning_sdk.billing import Billing, BillingActivityCursor, BillingActivityFilters
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace


def _make_org(org_id="org-1"):
    org = mock.MagicMock(spec=Organization)
    org.id = org_id
    return org


def _make_teamspace(teamspace_id, owner):
    teamspace = mock.MagicMock(spec=Teamspace)
    teamspace.id = teamspace_id
    teamspace.owner = owner
    return teamspace


@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_requires_org_or_org_owned_teamspace(mock_billing_api):
    with pytest.raises(ValueError, match="Could not resolve an organization"):
        Billing()


@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_rejects_both_teamspace_and_teamspaces(mock_billing_api):
    org = _make_org()
    teamspace = _make_teamspace("ts-1", org)

    with pytest.raises(ValueError, match="at most one"):
        Billing(org=org, teamspace=teamspace, teamspaces=[teamspace])


@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_with_org_only(mock_billing_api):
    org = _make_org("org-1")

    billing = Billing(org=org)

    assert billing._org is org
    assert billing._teamspaces == []


@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_with_single_teamspace_infers_org(mock_billing_api):
    org = _make_org("org-1")
    teamspace = _make_teamspace("ts-1", org)

    billing = Billing(teamspace=teamspace)

    assert billing._org is org
    assert billing._teamspaces == [teamspace]


@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_with_multiple_teamspaces(mock_billing_api):
    org = _make_org("org-1")
    ts1 = _make_teamspace("ts-1", org)
    ts2 = _make_teamspace("ts-2", org)

    billing = Billing(teamspaces=[ts1, ts2])

    assert billing._org is org
    assert billing._teamspaces == [ts1, ts2]


@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_with_org_and_teamspace(mock_billing_api):
    org = _make_org("org-1")
    other_org = _make_org("org-2")
    teamspace = _make_teamspace("ts-1", other_org)

    with pytest.raises(ValueError, match="belongs to organization"):
        Billing(org=org, teamspace=teamspace)


@mock.patch("lightning_sdk.billing._resolve_teamspace", return_value=None)
@mock.patch("lightning_sdk.billing.BillingApi")
def test_init_raises_if_teamspace_cannot_be_resolved(mock_billing_api, mock_resolve_teamspace):
    org = _make_org("org-1")

    with pytest.raises(ValueError, match="Could not resolve teamspace"):
        Billing(org=org, teamspace="missing-teamspace")


# ---- _project_ids -----------------------------------------------------------


@mock.patch("lightning_sdk.billing.BillingApi")
def test_project_ids_none_when_no_teamspaces(mock_billing_api):
    org = _make_org("org-1")
    billing = Billing(org=org)

    assert billing._project_ids() is None


@mock.patch("lightning_sdk.billing.BillingApi")
def test_project_ids_from_teamspaces(mock_billing_api):
    org = _make_org("org-1")
    ts1 = _make_teamspace("ts-1", org)
    ts2 = _make_teamspace("ts-2", org)
    billing = Billing(teamspaces=[ts1, ts2])

    assert billing._project_ids() == ["ts-1", "ts-2"]


# ---- get_activity -------------------------------------------------------


@mock.patch("lightning_sdk.billing.BillingApi")
def test_get_activity_defaults(mock_billing_api):
    org = _make_org("org-1")
    billing = Billing(org=org)

    result = billing.get_activity()

    assert result is billing._billing_api.get_activity.return_value
    billing._billing_api.get_activity.assert_called_once_with(
        org_id="org-1",
        project_ids=None,
        resource_types=None,
        resource_ids=None,
        user_ids=None,
        start=None,
        end=None,
        limit=None,
        search_after=None,
        search_after_resource_id=None,
        search_after_resource_type=None,
    )


@mock.patch("lightning_sdk.billing.BillingApi")
def test_get_activity_with_filters_and_cursor(mock_billing_api):
    org = _make_org("org-1")
    ts1 = _make_teamspace("ts-1", org)
    billing = Billing(teamspace=ts1)

    filters = BillingActivityFilters(resource_types=["Studio"], resource_ids=["res-1"], user_ids=["user-1"], limit=5)
    cursor = BillingActivityCursor(
        search_after="2026-01-01", search_after_resource_id="res-1", search_after_resource_type="Studio"
    )

    billing.get_activity(filters=filters, cursor=cursor)

    billing._billing_api.get_activity.assert_called_once_with(
        org_id="org-1",
        project_ids=["ts-1"],
        resource_types=["Studio"],
        resource_ids=["res-1"],
        user_ids=["user-1"],
        start=None,
        end=None,
        limit=5,
        search_after="2026-01-01",
        search_after_resource_id="res-1",
        search_after_resource_type="Studio",
    )


# ---- get_activity_filter_values -----------------------------------------


@mock.patch("lightning_sdk.billing.BillingApi")
def test_get_activity_filter_values_org_scope(mock_billing_api):
    org = _make_org("org-1")
    billing = Billing(org=org)

    result = billing.get_activity_filter_values()

    assert result is billing._billing_api.get_activity_filter_values.return_value
    billing._billing_api.get_activity_filter_values.assert_called_once_with(org_id="org-1", project_id=None)


@mock.patch("lightning_sdk.billing.BillingApi")
def test_get_activity_filter_values_single_teamspace_scope(mock_billing_api):
    org = _make_org("org-1")
    teamspace = _make_teamspace("ts-1", org)
    billing = Billing(teamspace=teamspace)

    billing.get_activity_filter_values()

    billing._billing_api.get_activity_filter_values.assert_called_once_with(org_id="org-1", project_id="ts-1")


@mock.patch("lightning_sdk.billing.BillingApi")
def test_get_activity_filter_values_rejects_multiple_teamspaces(mock_billing_api):
    org = _make_org("org-1")
    ts1 = _make_teamspace("ts-1", org)
    ts2 = _make_teamspace("ts-2", org)
    billing = Billing(teamspaces=[ts1, ts2])

    with pytest.raises(ValueError, match="only supports a single teamspace scope"):
        billing.get_activity_filter_values()


# ---- download_detailed_activity_csv / download_summary_activity_csv -----


@mock.patch("lightning_sdk.billing.BillingApi")
def test_download_detailed_activity_csv_forwards_args(mock_billing_api):
    org = _make_org("org-1")
    billing = Billing(org=org)

    billing.download_detailed_activity_csv("out.csv")

    billing._billing_api.download_detailed_activity_csv.assert_called_once_with(
        target_path="out.csv",
        org_id="org-1",
        project_ids=None,
        resource_types=None,
        resource_ids=None,
        user_ids=None,
        start=None,
        end=None,
        limit=None,
        search_after=None,
        search_after_resource_id=None,
        search_after_resource_type=None,
    )


@mock.patch("lightning_sdk.billing.BillingApi")
def test_download_summary_activity_csv_forwards_args(mock_billing_api):
    org = _make_org("org-1")
    teamspace = _make_teamspace("ts-1", org)
    billing = Billing(teamspace=teamspace)
    filters = BillingActivityFilters(limit=100)

    billing.download_summary_activity_csv("out.csv", filters=filters)

    billing._billing_api.download_summary_activity_csv.assert_called_once_with(
        target_path="out.csv",
        org_id="org-1",
        project_ids=["ts-1"],
        resource_types=None,
        resource_ids=None,
        user_ids=None,
        start=None,
        end=None,
        limit=100,
        search_after=None,
        search_after_resource_id=None,
        search_after_resource_type=None,
    )
