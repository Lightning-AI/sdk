"""Contract tests for BillingApi against the vendored OpenAPI client.

The unit tests in ``test_billing_api.py`` mock the generated client, so they keep passing even
when the vendored client doesn't accept the kwargs BillingApi sends or doesn't return the fields
it reads. These tests run the real generated client and only stub the HTTP request, checking the
query string that would go over the wire and that the response deserializes end to end.
"""

import json
from datetime import datetime, timezone
from unittest import mock

import pytest

from lightning_sdk.api.billing_api import (
    BillingActivitySubfilters,
    BillingApi,
    BillingAssistantMessageSubfilter,
    BillingNamedFilterValue,
    BillingWorkloadTagSubfilter,
)
from lightning_sdk.lightning_cloud.openapi import ApiClient, BillingServiceApi, Configuration


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self.status = 200
        self.reason = "OK"
        self.data = json.dumps(body)

    def getheaders(self) -> dict:
        return {}

    def getheader(self, name: str, default=None):
        return default


@pytest.fixture
def billing_api():
    """A BillingApi backed by the real generated client, with only the HTTP layer stubbed.

    Yields the api and a function that sets the response body and returns the request mock.
    """
    configuration = Configuration()
    configuration.host = "https://lightning.test"
    api_client = ApiClient(configuration)
    request = mock.MagicMock(return_value=_FakeResponse({}))
    api_client.request = request

    with mock.patch("lightning_sdk.api.billing_api.cached_lightning_client"):
        api = BillingApi()
    api._client = BillingServiceApi(api_client)

    def respond_with(body: dict) -> mock.MagicMock:
        request.return_value = _FakeResponse(body)
        return request

    return api, respond_with


def _sent_request(request: mock.MagicMock):
    """The (method, url, query params as a list of pairs) of the single request sent."""
    request.assert_called_once()
    method, url = request.call_args.args[:2]
    return method, url, list(request.call_args.kwargs["query_params"])


def _values(query_params, key):
    return [value for k, value in query_params if k == key]


def test_get_activity_sends_every_filter(billing_api):
    api, respond_with = billing_api
    request = respond_with({})

    api.get_activity(
        org_id="org-1",
        project_ids=["proj-1", "proj-2"],
        resource_types=["job"],
        resource_ids=["res-1"],
        user_ids=["user-1"],
        cluster_ids=["cluster-1", "cluster-2"],
        subfilters=BillingActivitySubfilters(
            job=BillingWorkloadTagSubfilter(tag_ids=["tag-1", "tag-2"], match_all_tags=True),
            multi_machine_job=BillingWorkloadTagSubfilter(tag_ids=["tag-3"]),
            deployment=BillingWorkloadTagSubfilter(tag_ids=["tag-4"]),
            assistant_message=BillingAssistantMessageSubfilter(api_key_ids=["key-1"]),
        ),
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        limit=50,
        search_after=datetime(2026, 1, 15, tzinfo=timezone.utc),
        search_after_resource_id="res-0",
        search_after_resource_type="job",
    )

    method, url, query = _sent_request(request)
    assert method == "GET"
    assert url == "https://lightning.test/v1/billing/usage-report-rollup"
    assert _values(query, "orgId") == ["org-1"]
    assert _values(query, "projectIds") == ["proj-1", "proj-2"]
    assert _values(query, "resourceTypes") == ["job"]
    assert _values(query, "resourceIds") == ["res-1"]
    assert _values(query, "userIds") == ["user-1"]
    assert _values(query, "clusterIds") == ["cluster-1", "cluster-2"]
    assert _values(query, "subfilters.job.tagIds") == ["tag-1", "tag-2"]
    assert _values(query, "subfilters.job.matchAllTags") == [True]
    assert _values(query, "subfilters.multiMachineJob.tagIds") == ["tag-3"]
    assert _values(query, "subfilters.multiMachineJob.matchAllTags") == []
    assert _values(query, "subfilters.deployment.tagIds") == ["tag-4"]
    assert _values(query, "subfilters.assistantMessage.apiKeyIds") == ["key-1"]
    assert _values(query, "limit") == [50]
    assert _values(query, "searchAfterResourceId") == ["res-0"]
    assert _values(query, "searchAfterResourceType") == ["job"]


def test_get_activity_sends_only_org_id_without_filters(billing_api):
    api, respond_with = billing_api
    request = respond_with({})

    api.get_activity(org_id="org-1")

    _, _, query = _sent_request(request)
    assert query == [("orgId", "org-1")]


def test_get_activity_deserializes_response(billing_api):
    api, respond_with = billing_api
    respond_with(
        {
            "totalCost": 12.5,
            "totalSavedCost": 2.5,
            "hasMore": True,
            "searchAfterResourceId": "res-1",
            "searchAfterResourceType": "job",
            "usage": [
                {
                    "id": "res-1",
                    "projectId": "proj-1",
                    "clusterId": "cluster-1",
                    "resourceType": "job",
                    "resourceName": "train",
                    "billedTimeSeconds": "120",
                    "cost": 12.5,
                }
            ],
            "dailyUsage": [{"totalCost": 12.5, "totalNumMessages": "3"}],
        }
    )

    activity = api.get_activity(org_id="org-1")

    assert activity.total_cost == 12.5
    assert activity.total_saved_cost == 2.5
    assert activity.has_more is True
    assert activity.search_after_resource_id == "res-1"
    assert activity.search_after_resource_type == "job"
    assert len(activity.usage) == 1
    usage = activity.usage[0]
    assert usage.id == "res-1"
    assert usage.cluster_id == "cluster-1"
    assert usage.resource_name == "train"
    assert usage.billed_time_seconds == 120
    assert activity.daily_usage[0].total_num_messages == 3


def test_get_activity_filter_values(billing_api):
    api, respond_with = billing_api
    request = respond_with(
        {
            "projectIds": ["proj-1"],
            "userIds": ["user-1"],
            "clusterIds": ["cluster-1"],
            "resourceTypes": ["lightning_code", "job"],
            "namedResourceTypes": [{"id": "lightning_code", "name": "Studio"}, {"id": "job", "name": "Job"}],
            "subfilters": {
                "job": {"resourceType": "Job", "tags": [{"id": "tag-1", "name": "nightly"}]},
                "multiMachineJob": {"resourceType": "Multi-Machine Job", "tags": []},
                "deployment": {"resourceType": "Deployment", "tags": [{"id": "tag-2", "name": "prod"}]},
                "assistantMessage": {"apiKeyIds": [{"id": "key-1", "name": "ci key"}]},
            },
        }
    )

    filter_values = api.get_activity_filter_values(org_id="org-1", project_id="proj-1")

    method, url, query = _sent_request(request)
    assert method == "GET"
    assert url == "https://lightning.test/v1/billing/usage-report/filter-values"
    assert query == [("orgId", "org-1"), ("projectId", "proj-1")]

    assert filter_values.project_ids == ["proj-1"]
    assert filter_values.user_ids == ["user-1"]
    assert filter_values.cluster_ids == ["cluster-1"]
    assert filter_values.resource_types == [
        BillingNamedFilterValue(id="lightning_code", name="Studio"),
        BillingNamedFilterValue(id="job", name="Job"),
    ]
    subfilters = filter_values.subfilters
    assert subfilters.job.resource_type == "Job"
    assert subfilters.job.tags == [BillingNamedFilterValue(id="tag-1", name="nightly")]
    assert subfilters.multi_machine_job.resource_type == "Multi-Machine Job"
    assert subfilters.multi_machine_job.tags == []
    assert subfilters.deployment.tags == [BillingNamedFilterValue(id="tag-2", name="prod")]
    assert subfilters.assistant_message.api_key_ids == [BillingNamedFilterValue(id="key-1", name="ci key")]


def test_get_activity_filter_resource_names(billing_api):
    api, respond_with = billing_api
    request = respond_with(
        {
            "resourceIds": [{"id": "res-1", "name": "my-studio"}, {"id": "res-2", "name": "train"}],
            "nextPageToken": "page-2",
        }
    )

    page = api.get_activity_filter_resource_names(
        org_id="org-1", project_id="proj-1", search_query="tra", page_size=2, page_token="page-1"
    )

    method, url, query = _sent_request(request)
    assert method == "GET"
    assert url == "https://lightning.test/v1/billing/usage-report/filter-values/resource-names"
    assert _values(query, "orgId") == ["org-1"]
    assert _values(query, "projectId") == ["proj-1"]
    assert _values(query, "searchQuery") == ["tra"]
    assert _values(query, "pageSize") == [2]
    assert _values(query, "pageToken") == ["page-1"]

    assert page.resource_ids == [
        BillingNamedFilterValue(id="res-1", name="my-studio"),
        BillingNamedFilterValue(id="res-2", name="train"),
    ]
    assert page.next_page_token == "page-2"


def test_get_activity_filter_resource_names_last_page(billing_api):
    api, respond_with = billing_api
    respond_with({"resourceIds": [], "nextPageToken": ""})

    page = api.get_activity_filter_resource_names(org_id="org-1")

    assert page.resource_ids == []
    assert page.next_page_token is None
