import io
from datetime import datetime
from unittest import mock

import pytest

from lightning_sdk.api.billing_api import ActivityFileFormat
from lightning_sdk.organization import BillingActivityCursor, BillingActivityFilters, Organization
from lightning_sdk.teamspace import Teamspace


def _make_org(org_id="org-1"):
    org = mock.MagicMock(spec=Organization)
    org.id = org_id
    org.name = org_id
    org._billing_api = mock.MagicMock()
    org._resolve_billing_teamspaces = Organization._resolve_billing_teamspaces.__get__(org)
    org.get_activity = Organization.get_activity.__get__(org)
    org.get_activity_filter_values = Organization.get_activity_filter_values.__get__(org)
    org.get_session_activity = Organization.get_session_activity.__get__(org)
    org.get_resource_activity = Organization.get_resource_activity.__get__(org)
    return org


def _make_teamspace(teamspace_id, owner):
    teamspace = mock.MagicMock(spec=Teamspace)
    teamspace.id = teamspace_id
    teamspace.owner = owner
    return teamspace


# ---- _resolve_billing_teamspaces ----------------------------------------


def test_resolve_billing_teamspaces_rejects_both_teamspace_and_teamspaces():
    org = _make_org()
    teamspace = _make_teamspace("ts-1", org)

    with pytest.raises(ValueError, match="at most one"):
        org._resolve_billing_teamspaces(teamspace=teamspace, teamspaces=[teamspace])


def test_resolve_billing_teamspaces_none_when_no_teamspaces():
    org = _make_org("org-1")

    assert org._resolve_billing_teamspaces() == []


@mock.patch("lightning_sdk.organization._resolve_teamspace")
def test_resolve_billing_teamspaces_from_teamspaces(mock_resolve_teamspace):
    org = _make_org("org-1")
    ts1 = _make_teamspace("ts-1", org)
    ts2 = _make_teamspace("ts-2", org)
    mock_resolve_teamspace.side_effect = [ts1, ts2]

    assert org._resolve_billing_teamspaces(teamspaces=[ts1, ts2]) == [ts1, ts2]


@mock.patch("lightning_sdk.organization._resolve_teamspace")
def test_resolve_billing_teamspaces_rejects_teamspace_from_other_org(mock_resolve_teamspace):
    org = _make_org("org-1")
    other_org = _make_org("org-2")
    teamspace = _make_teamspace("ts-1", other_org)
    mock_resolve_teamspace.return_value = teamspace

    with pytest.raises(ValueError, match="belongs to organization"):
        org._resolve_billing_teamspaces(teamspace=teamspace)


@mock.patch("lightning_sdk.organization._resolve_teamspace", return_value=None)
def test_resolve_billing_teamspaces_raises_if_teamspace_cannot_be_resolved(mock_resolve_teamspace):
    org = _make_org("org-1")

    with pytest.raises(ValueError, match="Could not resolve teamspace"):
        org._resolve_billing_teamspaces(teamspace="missing-teamspace")


# ---- get_activity -------------------------------------------------------


def test_get_activity_defaults():
    org = _make_org("org-1")

    result = org.get_activity()

    assert result is org._billing_api.get_activity.return_value
    org._billing_api.get_activity.assert_called_once_with(
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


@mock.patch("lightning_sdk.organization._resolve_teamspace")
def test_get_activity_with_filters_and_cursor(mock_resolve_teamspace):
    org = _make_org("org-1")
    ts1 = _make_teamspace("ts-1", org)
    mock_resolve_teamspace.return_value = ts1

    filters = BillingActivityFilters(resource_types=["Studio"], resource_ids=["res-1"], user_ids=["user-1"], limit=5)
    cursor = BillingActivityCursor(
        search_after=datetime(2026, 1, 1), search_after_resource_id="res-1", search_after_resource_type="Studio"
    )

    org.get_activity(teamspace=ts1, filters=filters, cursor=cursor)

    org._billing_api.get_activity.assert_called_once_with(
        org_id="org-1",
        project_ids=["ts-1"],
        resource_types=["Studio"],
        resource_ids=["res-1"],
        user_ids=["user-1"],
        start=None,
        end=None,
        limit=5,
        search_after=datetime(2026, 1, 1),
        search_after_resource_id="res-1",
        search_after_resource_type="Studio",
    )


# ---- get_activity_filter_values -----------------------------------------


def test_get_activity_filter_values_org_scope():
    org = _make_org("org-1")

    result = org.get_activity_filter_values()

    assert result is org._billing_api.get_activity_filter_values.return_value
    org._billing_api.get_activity_filter_values.assert_called_once_with(org_id="org-1", project_id=None)


@mock.patch("lightning_sdk.organization._resolve_teamspace")
def test_get_activity_filter_values_single_teamspace_scope(mock_resolve_teamspace):
    org = _make_org("org-1")
    teamspace = _make_teamspace("ts-1", org)
    mock_resolve_teamspace.return_value = teamspace

    org.get_activity_filter_values(teamspace=teamspace)

    org._billing_api.get_activity_filter_values.assert_called_once_with(org_id="org-1", project_id="ts-1")


# ---- get_session_activity / get_resource_activity -----------------------


def test_get_session_activity_forwards_args():
    org = _make_org("org-1")
    writer = io.StringIO()

    org.get_session_activity(format=ActivityFileFormat.CSV, writer=writer)

    org._billing_api.get_session_activity.assert_called_once_with(
        org_id="org-1",
        format=ActivityFileFormat.CSV,
        writer=writer,
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


def test_get_session_activity_defaults_to_json():
    org = _make_org("org-1")
    writer = io.StringIO()

    org.get_session_activity(writer=writer)

    org._billing_api.get_session_activity.assert_called_once_with(
        org_id="org-1",
        format=ActivityFileFormat.JSON,
        writer=writer,
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


@mock.patch("lightning_sdk.organization._resolve_teamspace")
def test_get_resource_activity_forwards_args(mock_resolve_teamspace):
    org = _make_org("org-1")
    teamspace = _make_teamspace("ts-1", org)
    mock_resolve_teamspace.return_value = teamspace
    filters = BillingActivityFilters(limit=100)
    writer = io.StringIO()

    org.get_resource_activity(format=ActivityFileFormat.CSV, writer=writer, teamspace=teamspace, filters=filters)

    org._billing_api.get_resource_activity.assert_called_once_with(
        org_id="org-1",
        format=ActivityFileFormat.CSV,
        writer=writer,
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


def test_get_resource_activity_defaults_to_json():
    org = _make_org("org-1")
    writer = io.StringIO()

    org.get_resource_activity(writer=writer)

    org._billing_api.get_resource_activity.assert_called_once_with(
        org_id="org-1",
        format=ActivityFileFormat.JSON,
        writer=writer,
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
