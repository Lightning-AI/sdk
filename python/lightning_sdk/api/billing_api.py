"""Low-level client and response types for the billing/usage-report endpoints.

:class:`BillingApi` wraps both the generated OpenAPI client (for the JSON usage report and
filter-values endpoints) and hand-rolled authenticated HTTP requests (for the CSV download
endpoints, which aren't exposed by the generated client). The ``lightning_sdk.billing`` module
provides the higher-level, user-facing interface built on top of this one.

Three ways to get billing activity, at different grains:
    - :meth:`BillingApi.get_activity`: paginated rollup rows, one per resource over the queried
      range, keyed by raw teamspace/user/cloud account IDs. Meant for programmatic/incremental
      consumption.
    - :meth:`BillingApi.get_session_activity`: one row per session, with resolved names. A
      resource (e.g. a Studio or Job) can have many sessions in the queried range. Returns CSV
      or JSON depending on the ``format`` argument.
    - :meth:`BillingApi.get_resource_activity`: one row per resource that was active in the
      queried range, with resolved names, a more concise view than the session-level report.
      Returns CSV or JSON depending on the ``format`` argument.

The values each filter accepts come from :meth:`BillingApi.get_activity_filter_values`, and
resource IDs from :meth:`BillingApi.get_activity_filter_resource_names`.
"""

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import IO, Any, Dict, List, Optional

import requests

from lightning_sdk.api.utils import (
    _authenticate_and_get_auth_headers,
    _raise_for_download_status,
    cached_lightning_client,
)


@dataclass
class BillingResourceUsage:
    """A single resource's usage/cost within a billing activity report.

    Attributes:
        id: ID of the resource.
        user_id: ID of the user that owns/started the resource.
        project_id: ID of the teamspace (project) the resource belongs to.
        cluster_id: ID of the cloud account the resource ran on.
        resource_type: Type of the resource (e.g. "lightning_code" for a Studio, "job").
        resource_name: Name of the resource.
        created_at: When the resource was created.
        deleted_at: When the resource was deleted, if it has been.
        billed_time_seconds: Total billed time for this resource, in seconds.
        cost: Total credits spent by this resource.
        saved_cost: Total credits saved by this resource.
        bucket_start: Start of the usage rollup bucket this row represents.
    """

    id: Optional[str] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    cluster_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    billed_time_seconds: Optional[int] = None
    cost: Optional[float] = None
    saved_cost: Optional[float] = None
    bucket_start: Optional[datetime] = None

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingResourceUsage":
        billed_time_seconds = data.get("billed_time_seconds")
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id"),
            project_id=data.get("project_id"),
            cluster_id=data.get("cluster_id"),
            resource_type=data.get("resource_type"),
            resource_name=data.get("resource_name"),
            created_at=data.get("created_at"),
            deleted_at=data.get("deleted_at"),
            billed_time_seconds=int(billed_time_seconds) if billed_time_seconds is not None else None,
            cost=data.get("cost"),
            saved_cost=data.get("saved_cost"),
            bucket_start=data.get("bucket_start"),
        )


@dataclass
class BillingDailyUsage:
    """Aggregated usage/cost for a single day within a billing activity report.

    Attributes:
        day: The day this entry aggregates.
        total_cost: Total credits spent on this day.
        total_saved_cost: Total credits saved on this day.
        total_prompt_tokens: Total prompt tokens consumed on this day.
        total_completion_tokens: Total completion tokens consumed on this day.
        total_num_messages: Total number of messages sent on this day.
    """

    day: Optional[datetime] = None
    total_cost: Optional[float] = None
    total_saved_cost: Optional[float] = None
    total_prompt_tokens: Optional[int] = None
    total_completion_tokens: Optional[int] = None
    total_num_messages: Optional[int] = None

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingDailyUsage":
        total_prompt_tokens = data.get("total_prompt_tokens")
        total_completion_tokens = data.get("total_completion_tokens")
        total_num_messages = data.get("total_num_messages")
        return cls(
            day=data.get("day"),
            total_cost=data.get("total_cost"),
            total_saved_cost=data.get("total_saved_cost"),
            total_prompt_tokens=int(total_prompt_tokens) if total_prompt_tokens is not None else 0,
            total_completion_tokens=int(total_completion_tokens) if total_completion_tokens is not None else 0,
            total_num_messages=int(total_num_messages) if total_num_messages is not None else 0,
        )


@dataclass
class BillingActivity:
    """Billing activity for an org/teamspace scope, as returned by the V2 usage report endpoint.

    Attributes:
        total_cost: Total credits spent by all filtered resources during the queried time range.
        total_saved_cost: Total credits saved by all filtered resources during the queried time
            range.
        usage: Per-resource usage/cost, one entry per filtered resource.
        daily_usage: Usage/cost aggregated by day.
        has_more: Whether more entries are available past ``limit``. If ``True``, pass a
            :class:`~lightning_sdk.organization.BillingActivityCursor` built from ``search_after``,
            ``search_after_resource_id``, and ``search_after_resource_type`` to fetch the next page.
        search_after: Cursor value to continue pagination from. Only set when ``limit`` was
            provided on the request.
        search_after_resource_id: Paired with ``search_after`` to break ties between resources
            sharing the same ``search_after`` time.
        search_after_resource_type: Paired with ``search_after`` to break ties between resources
            sharing the same ``search_after`` time.
    """

    total_cost: Optional[float] = None
    total_saved_cost: Optional[float] = None
    usage: List[BillingResourceUsage] = field(default_factory=list)
    daily_usage: List[BillingDailyUsage] = field(default_factory=list)
    has_more: bool = False
    search_after: Optional[datetime] = None
    search_after_resource_id: Optional[str] = None
    search_after_resource_type: Optional[str] = None

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingActivity":
        return cls(
            total_cost=data.get("total_cost"),
            total_saved_cost=data.get("total_saved_cost"),
            usage=[BillingResourceUsage._from_api(item) for item in data.get("usage") or []],
            daily_usage=[BillingDailyUsage._from_api(item) for item in data.get("daily_usage") or []],
            has_more=bool(data.get("has_more")),
            search_after=data.get("search_after"),
            search_after_resource_id=data.get("search_after_resource_id"),
            search_after_resource_type=data.get("search_after_resource_type"),
        )


@dataclass
class BillingNamedFilterValue:
    """A filterable ID paired with its display name.

    Attributes:
        id: The ID to filter by.
        name: Display name for the ID. Falls back to the ID itself when no name could be
            resolved.
    """

    id: Optional[str] = None
    name: Optional[str] = None

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingNamedFilterValue":
        return cls(id=data.get("id"), name=data.get("name"))


def _named_filter_values(items: Optional[List[Dict[str, Any]]]) -> List[BillingNamedFilterValue]:
    return [BillingNamedFilterValue._from_api(item) for item in items or []]


@dataclass
class BillingWorkloadSubfilterValues:
    """Tags a workload resource type (jobs, multi-machine jobs or deployments) can be filtered by.

    Attributes:
        resource_type: Display name of the resource type these tags belong to, e.g. "Job".
        tags: Tags on at least one workload of this type. Pass their IDs as
            :attr:`BillingWorkloadTagSubfilter.tag_ids`.
    """

    resource_type: Optional[str] = None
    tags: List[BillingNamedFilterValue] = field(default_factory=list)

    @classmethod
    def _from_api(cls, data: Optional[Dict[str, Any]]) -> "BillingWorkloadSubfilterValues":
        data = data or {}
        return cls(resource_type=data.get("resource_type"), tags=_named_filter_values(data.get("tags")))


@dataclass
class BillingAssistantMessageSubfilterValues:
    """API keys assistant messages can be filtered by.

    Attributes:
        api_key_ids: API keys that billed at least one message. ``name`` is the key's display
            name, never its secret. Pass their IDs as
            :attr:`BillingAssistantMessageSubfilter.api_key_ids`.
    """

    api_key_ids: List[BillingNamedFilterValue] = field(default_factory=list)

    @classmethod
    def _from_api(cls, data: Optional[Dict[str, Any]]) -> "BillingAssistantMessageSubfilterValues":
        data = data or {}
        return cls(api_key_ids=_named_filter_values(data.get("api_key_ids")))


@dataclass
class BillingActivitySubfilterValues:
    """Filter values that only apply to one resource type, one field per type.

    Attributes:
        job: Tags available to filter jobs by.
        multi_machine_job: Tags available to filter multi-machine jobs by.
        deployment: Tags available to filter deployments by.
        assistant_message: API keys available to filter assistant messages by.
    """

    job: BillingWorkloadSubfilterValues = field(default_factory=BillingWorkloadSubfilterValues)
    multi_machine_job: BillingWorkloadSubfilterValues = field(default_factory=BillingWorkloadSubfilterValues)
    deployment: BillingWorkloadSubfilterValues = field(default_factory=BillingWorkloadSubfilterValues)
    assistant_message: BillingAssistantMessageSubfilterValues = field(
        default_factory=BillingAssistantMessageSubfilterValues
    )

    @classmethod
    def _from_api(cls, data: Optional[Dict[str, Any]]) -> "BillingActivitySubfilterValues":
        data = data or {}
        return cls(
            job=BillingWorkloadSubfilterValues._from_api(data.get("job")),
            multi_machine_job=BillingWorkloadSubfilterValues._from_api(data.get("multi_machine_job")),
            deployment=BillingWorkloadSubfilterValues._from_api(data.get("deployment")),
            assistant_message=BillingAssistantMessageSubfilterValues._from_api(data.get("assistant_message")),
        )


@dataclass
class BillingActivityFilterValues:
    """The set of values a billing activity query can be filtered by, for a given scope.

    Resource IDs aren't included, since an org can have too many to return at once; page through
    them with :meth:`BillingApi.get_activity_filter_resource_names` instead.

    Attributes:
        project_ids: Teamspace (project) IDs with billing activity in the queried scope.
        user_ids: User IDs with billing activity in the queried scope.
        resource_types: Resource types with billing activity in the queried scope, e.g.
            "lightning_code" (Studios), "job" or "assistant_message".
        cluster_ids: Cloud account IDs with billing activity in the queried scope.
        subfilters: Values for the filters that only apply to one resource type.
    """

    project_ids: List[str] = field(default_factory=list)
    user_ids: List[str] = field(default_factory=list)
    resource_types: List[str] = field(default_factory=list)
    cluster_ids: List[str] = field(default_factory=list)
    subfilters: BillingActivitySubfilterValues = field(default_factory=BillingActivitySubfilterValues)

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingActivityFilterValues":
        return cls(
            project_ids=list(data.get("project_ids") or []),
            user_ids=list(data.get("user_ids") or []),
            resource_types=list(data.get("resource_types") or []),
            cluster_ids=list(data.get("cluster_ids") or []),
            subfilters=BillingActivitySubfilterValues._from_api(data.get("subfilters")),
        )


@dataclass
class BillingActivityResourceNames:
    """One page of resource IDs a billing activity query can be filtered by.

    Attributes:
        resource_ids: Resource IDs paired with their display names.
        next_page_token: Pass as ``page_token`` to fetch the next page. Empty on the last page.
    """

    resource_ids: List[BillingNamedFilterValue] = field(default_factory=list)
    next_page_token: Optional[str] = None

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingActivityResourceNames":
        return cls(
            resource_ids=_named_filter_values(data.get("resource_ids")),
            next_page_token=data.get("next_page_token") or None,
        )


@dataclass
class BillingWorkloadTagSubfilter:
    """Keeps only the workloads of one resource type that carry the given tags.

    Attributes:
        tag_ids: Keep workloads with any of these tags. Available tags are listed in
            :attr:`BillingActivityFilterValues.subfilters`. Empty means no subfilter for this
            resource type.
        match_all_tags: Require every tag in ``tag_ids`` rather than any.
    """

    tag_ids: List[str] = field(default_factory=list)
    match_all_tags: bool = False


@dataclass
class BillingAssistantMessageSubfilter:
    """Keeps only the assistant messages billed through the given API keys.

    Attributes:
        api_key_ids: Keep messages billed through any of these API keys. Available keys are
            listed in :attr:`BillingActivityFilterValues.subfilters`. Empty means no subfilter
            for assistant messages.
    """

    api_key_ids: List[str] = field(default_factory=list)


@dataclass
class BillingActivitySubfilters:
    """Filters that only apply to one resource type, one field per type.

    Setting a field keeps only the rows of its resource type that match it. With several set, a
    row matching any of them is kept. Once any field is set, rows of resource types without a
    subfilter are dropped.

    Attributes:
        job: Applies to job rows.
        multi_machine_job: Applies to multi-machine job rows.
        deployment: Applies to deployment rows.
        assistant_message: Applies to assistant message rows.
    """

    job: Optional[BillingWorkloadTagSubfilter] = None
    multi_machine_job: Optional[BillingWorkloadTagSubfilter] = None
    deployment: Optional[BillingWorkloadTagSubfilter] = None
    assistant_message: Optional[BillingAssistantMessageSubfilter] = None

    def _workload_tag_subfilters(self) -> Dict[str, BillingWorkloadTagSubfilter]:
        """The workload tag subfilters that are set, keyed by their field name."""
        workloads = {"job": self.job, "multi_machine_job": self.multi_machine_job, "deployment": self.deployment}
        return {name: subfilter for name, subfilter in workloads.items() if subfilter is not None and subfilter.tag_ids}

    def _api_key_ids(self) -> List[str]:
        return self.assistant_message.api_key_ids if self.assistant_message is not None else []


# grpc-gateway reads nested request fields from dotted, lowerCamelCase query keys.
_SUBFILTER_QUERY_KEYS = {"job": "job", "multi_machine_job": "multiMachineJob", "deployment": "deployment"}


def _subfilter_client_kwargs(subfilters: Optional[BillingActivitySubfilters]) -> Dict[str, Any]:
    """Flatten subfilters into the kwargs the generated client takes for them."""
    if subfilters is None:
        return {}

    kwargs: Dict[str, Any] = {}
    for name, subfilter in subfilters._workload_tag_subfilters().items():
        kwargs[f"subfilters_{name}_tag_ids"] = subfilter.tag_ids
        if subfilter.match_all_tags:
            kwargs[f"subfilters_{name}_match_all_tags"] = True
    if api_key_ids := subfilters._api_key_ids():
        kwargs["subfilters_assistant_message_api_key_ids"] = api_key_ids
    return kwargs


def _subfilter_query_params(subfilters: Optional[BillingActivitySubfilters]) -> Dict[str, Any]:
    """Build the subfilter query params the CSV download endpoints read.

    The download endpoints only read the assistant message subfilter so far, so a workload tag
    subfilter is rejected rather than silently returning unfiltered rows.
    """
    if subfilters is None:
        return {}

    if workload_subfilters := subfilters._workload_tag_subfilters():
        raise ValueError(
            f"Tag subfilters ({', '.join(workload_subfilters)}) aren't supported by the session and resource "
            "activity reports yet; use get_activity to filter by tags."
        )

    query_params: Dict[str, Any] = {}
    if api_key_ids := subfilters._api_key_ids():
        query_params["subfilters.assistantMessage.apiKeyIds"] = api_key_ids
    return query_params


class ActivityFileFormat(str, Enum):
    """File format to return a billing activity report in."""

    JSON = "json"
    CSV = "csv"

    def __str__(self) -> str:
        """Converts the ActivityFileFormat to a str.

        Returns:
            str: The string value of the enum member (e.g. ``"json"``).
        """
        return self.value


def _build_activity_query_params(
    org_id: str,
    project_ids: Optional[List[str]] = None,
    resource_types: Optional[List[str]] = None,
    resource_ids: Optional[List[str]] = None,
    user_ids: Optional[List[str]] = None,
    cluster_ids: Optional[List[str]] = None,
    subfilters: Optional[BillingActivitySubfilters] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build the query params the CSV download endpoints read.

    These endpoints return the whole report at once, so unlike the V2 usage report they take no
    ``limit`` or pagination cursor.
    """
    query_params: Dict[str, Any] = {"orgId": org_id}
    if project_ids is not None:
        query_params["projectIds"] = project_ids
    if resource_types is not None:
        query_params["resourceTypes"] = resource_types
    if resource_ids is not None:
        query_params["resourceIds"] = resource_ids
    if user_ids is not None:
        query_params["userIds"] = user_ids
    if cluster_ids is not None:
        query_params["clusterIds"] = cluster_ids
    query_params.update(_subfilter_query_params(subfilters))
    if start is not None:
        query_params["from"] = start.isoformat()
    if end is not None:
        query_params["to"] = end.isoformat()
    return query_params


class BillingApi:
    """Internal API client for billing/usage-report requests.

    Combines calls through the generated OpenAPI client (:meth:`get_activity`,
    :meth:`get_activity_filter_values`, :meth:`get_activity_filter_resource_names`) with raw
    authenticated HTTP requests for the CSV download endpoints (:meth:`get_session_activity`,
    :meth:`get_resource_activity`), which aren't exposed by the generated client. Both return CSV
    or JSON depending on the ``format`` argument; the JSON variant is built on top of the CSV
    download, converting it in memory.
    """

    def __init__(self) -> None:
        self._client = cached_lightning_client()

    def _download_activity_csv(
        self,
        endpoint: str,
        org_id: str,
        project_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        cluster_ids: Optional[List[str]] = None,
        subfilters: Optional[BillingActivitySubfilters] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> str:
        """Download a billing activity report and return its raw CSV text."""
        query_params = _build_activity_query_params(
            org_id=org_id,
            project_ids=project_ids,
            resource_types=resource_types,
            resource_ids=resource_ids,
            user_ids=user_ids,
            cluster_ids=cluster_ids,
            subfilters=subfilters,
            start=start,
            end=end,
        )

        r = requests.get(
            f"{self._client.api_client.configuration.host}{endpoint}",
            params=query_params,
            headers=_authenticate_and_get_auth_headers(),
            stream=True,
            allow_redirects=True,
        )

        _raise_for_download_status(r, endpoint)

        return r.text

    def _get_activity_report(
        self,
        endpoint: str,
        org_id: str,
        format: ActivityFileFormat,  # noqa: A002
        writer: IO[str],
        project_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        cluster_ids: Optional[List[str]] = None,
        subfilters: Optional[BillingActivitySubfilters] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """Get a CSV-download-backed billing activity report, as CSV or JSON.

        Shared by :meth:`get_session_activity` and :meth:`get_resource_activity`, which only
        differ in which download endpoint they hit.

        If ``format`` is :attr:`ActivityFileFormat.CSV`, the raw CSV text is written to
        ``writer``. If ``format`` is :attr:`ActivityFileFormat.JSON`, the CSV is parsed and the
        equivalent JSON is written to ``writer`` instead. To get the JSON as a string rather
        than writing it to a file, pass an ``io.StringIO()`` as ``writer`` and read it back with
        ``.getvalue()``.
        """
        format = ActivityFileFormat(format)  # noqa: A001

        csv_text = self._download_activity_csv(
            endpoint,
            org_id=org_id,
            project_ids=project_ids,
            resource_types=resource_types,
            resource_ids=resource_ids,
            user_ids=user_ids,
            cluster_ids=cluster_ids,
            subfilters=subfilters,
            start=start,
            end=end,
        )

        if format is ActivityFileFormat.CSV:
            writer.write(csv_text)
            return

        rows = list(csv.DictReader(io.StringIO(csv_text)))
        json.dump(rows, writer, indent=2)

    def get_session_activity(
        self,
        org_id: str,
        writer: IO[str],
        format: ActivityFileFormat = ActivityFileFormat.JSON,  # noqa: A002
        project_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        cluster_ids: Optional[List[str]] = None,
        subfilters: Optional[BillingActivitySubfilters] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """Get the session-level billing activity report, as CSV or JSON.

        One row per session. A resource (e.g. a Studio or Job) can have many sessions within
        the queried time range, so this report is the finer-grained of the two; use
        :meth:`get_resource_activity` for one row per resource instead.

        Hits ``GET /v1/billing/usage-report/download/detailed`` with the same filters as the V2
        usage report (see :meth:`get_activity`), except tag subfilters, and returns the whole
        report at once rather than paginating. Not exposed by the generated OpenAPI client, so
        this issues a raw authenticated HTTP request directly against ``self._client``'s
        configured host (see ``StudioApi.download_file`` for the established pattern of doing so).

        If ``format`` is :attr:`ActivityFileFormat.CSV`, the raw CSV text is written straight to
        ``writer``. If ``format`` is :attr:`ActivityFileFormat.JSON` (the default), the CSV is
        parsed and the equivalent JSON is written to ``writer`` instead. ``writer`` can be any
        writable text stream: an open file, an ``io.StringIO`` buffer, ``sys.stdout``, etc. To
        get the JSON as a string rather than writing it to a file, pass an ``io.StringIO()`` and
        read it back with ``.getvalue()``.

        Args:
            org_id: ID of the organization to query.
            writer: Writable text stream to write the report to.
            format: File format to return the report in, CSV or JSON. Defaults to JSON.
            project_ids: Restrict to these teamspace (project) IDs. If omitted, activity over
                all teamspaces in the organization is returned.
            resource_types: Restrict to these resource types. If omitted, all resource types
                are returned.
            resource_ids: Restrict to these specific resource IDs. If omitted, all matching
                resources are returned.
            user_ids: Restrict to activity generated by these users.
            cluster_ids: Restrict to activity on these cloud accounts.
            subfilters: Restrict assistant messages to the given API keys. Tag subfilters aren't
                supported by this report yet and raise a ``ValueError``.
            start: Only include activity on or after this time. Defaults to project/resource
                creation time.
            end: Only include activity on or before this time. Defaults to resource deletion
                time or now.
        """
        self._get_activity_report(
            "/v1/billing/usage-report/download/detailed",
            org_id=org_id,
            format=format,
            writer=writer,
            project_ids=project_ids,
            resource_types=resource_types,
            resource_ids=resource_ids,
            user_ids=user_ids,
            cluster_ids=cluster_ids,
            subfilters=subfilters,
            start=start,
            end=end,
        )

    def get_resource_activity(
        self,
        org_id: str,
        writer: IO[str],
        format: ActivityFileFormat = ActivityFileFormat.JSON,  # noqa: A002
        project_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        cluster_ids: Optional[List[str]] = None,
        subfilters: Optional[BillingActivitySubfilters] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """Get the resource-level billing activity report, as CSV or JSON.

        One row per resource (e.g. a Studio or Job) that was active in the queried time range,
        rather than one row per session; use :meth:`get_session_activity` for the
        finer-grained, per-session breakdown of a resource's activity.

        Hits ``GET /v1/billing/usage-report/download/summary`` with the same filters as the V2
        usage report (see :meth:`get_activity`), except tag subfilters, and returns the whole
        report at once rather than paginating. Not exposed by the generated OpenAPI client, so
        this issues a raw authenticated HTTP request directly against ``self._client``'s
        configured host (see ``StudioApi.download_file`` for the established pattern of doing so).

        If ``format`` is :attr:`ActivityFileFormat.CSV`, the raw CSV text is written straight to
        ``writer``. If ``format`` is :attr:`ActivityFileFormat.JSON` (the default), the CSV is
        parsed and the equivalent JSON is written to ``writer`` instead. ``writer`` can be any
        writable text stream: an open file, an ``io.StringIO`` buffer, ``sys.stdout``, etc. To
        get the JSON as a string rather than writing it to a file, pass an ``io.StringIO()`` and
        read it back with ``.getvalue()``.

        Args:
            org_id: ID of the organization to query.
            writer: Writable text stream to write the report to.
            format: File format to return the report in, CSV or JSON. Defaults to JSON.
            project_ids: Restrict to these teamspace (project) IDs. If omitted, activity over
                all teamspaces in the organization is returned.
            resource_types: Restrict to these resource types. If omitted, all resource types
                are returned.
            resource_ids: Restrict to these specific resource IDs. If omitted, all matching
                resources are returned.
            user_ids: Restrict to activity generated by these users.
            cluster_ids: Restrict to activity on these cloud accounts.
            subfilters: Restrict assistant messages to the given API keys. Tag subfilters aren't
                supported by this report yet and raise a ``ValueError``.
            start: Only include activity on or after this time. Defaults to project/resource
                creation time.
            end: Only include activity on or before this time. Defaults to resource deletion
                time or now.
        """
        self._get_activity_report(
            "/v1/billing/usage-report/download/summary",
            org_id=org_id,
            format=format,
            writer=writer,
            project_ids=project_ids,
            resource_types=resource_types,
            resource_ids=resource_ids,
            user_ids=user_ids,
            cluster_ids=cluster_ids,
            subfilters=subfilters,
            start=start,
            end=end,
        )

    def get_activity(
        self,
        org_id: str,
        project_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        cluster_ids: Optional[List[str]] = None,
        subfilters: Optional[BillingActivitySubfilters] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
        search_after_resource_id: Optional[str] = None,
        search_after_resource_type: Optional[str] = None,
    ) -> BillingActivity:
        """Get billing activity for an organization, optionally scoped to specific teamspaces.

        Returns paginated rollup rows, one per resource over the queried range, keyed by raw
        teamspace/user/cloud account IDs. For a resolved-name, non-paginated report meant for
        reading or exporting, use :meth:`get_session_activity` (one row per session) or
        :meth:`get_resource_activity` (one row per resource) instead.

        Backed by ``billing_service_get_usage_report_v2`` (daily rollup billing activity endpoint).

        Args:
            org_id: ID of the organization to query.
            project_ids: Restrict to these teamspace (project) IDs. If omitted, activity over
                all teamspaces in the organization is returned.
            resource_types: Restrict to these resource types. If omitted, all resource types
                are returned.
            resource_ids: Restrict to these specific resource IDs. If omitted, all matching
                resources are returned.
            user_ids: Restrict to activity generated by these users.
            cluster_ids: Restrict to activity on these cloud accounts.
            subfilters: Restrict individual resource types further, by tag or API key.
            start: Only include activity on or after this time. Defaults to project/resource
                creation time.
            end: Only include activity on or before this time. Defaults to resource deletion
                time or now.
            limit: Maximum number of entries to return.
            search_after: Pagination cursor, only include entries strictly after this time.
            search_after_resource_id: Pagination cursor, resource ID to break ties with
                ``search_after``. Required alongside ``search_after_resource_type``.
            search_after_resource_type: Pagination cursor, resource type to break ties with
                ``search_after``. Required alongside ``search_after_resource_id``.

        Returns:
            BillingActivity: The usage report response.
        """
        kwargs: Dict[str, Any] = {"org_id": org_id}
        if project_ids is not None:
            kwargs["project_ids"] = project_ids
        if resource_types is not None:
            kwargs["resource_types"] = resource_types
        if resource_ids is not None:
            kwargs["resource_ids"] = resource_ids
        if user_ids is not None:
            kwargs["user_ids"] = user_ids
        if cluster_ids is not None:
            kwargs["cluster_ids"] = cluster_ids
        kwargs.update(_subfilter_client_kwargs(subfilters))
        if start is not None:
            kwargs["_from"] = start
        if end is not None:
            kwargs["to"] = end
        if limit is not None:
            kwargs["limit"] = limit
        if search_after is not None:
            kwargs["search_after"] = search_after
        if search_after_resource_id is not None:
            kwargs["search_after_resource_id"] = search_after_resource_id
        if search_after_resource_type is not None:
            kwargs["search_after_resource_type"] = search_after_resource_type

        response = self._client.billing_service_get_usage_report_v2(**kwargs)
        return BillingActivity._from_api(response.to_dict())

    def get_activity_filter_values(
        self,
        org_id: str,
        project_id: Optional[str] = None,
    ) -> BillingActivityFilterValues:
        """Get the set of values a billing activity query can be filtered by.

        Backed by ``billing_service_get_activity_filter_values``. Returns the projects, users,
        resource types, cloud accounts and per-resource-type subfilter values available to filter
        the activity page by, for the given scope. Resource IDs come from
        :meth:`get_activity_filter_resource_names`.

        Args:
            org_id: ID of the organization to query.
            project_id: If given, restrict the returned filter values to this teamspace
                (project). If omitted, filter values across the whole organization are returned.

        Returns:
            BillingActivityFilterValues: The available filter values.
        """
        kwargs: Dict[str, Any] = {"org_id": org_id}
        if project_id is not None:
            kwargs["project_id"] = project_id

        response = self._client.billing_service_get_activity_filter_values(**kwargs)
        return BillingActivityFilterValues._from_api(response.to_dict())

    def get_activity_filter_resource_names(
        self,
        org_id: str,
        project_id: Optional[str] = None,
        search_query: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> BillingActivityResourceNames:
        """Get one page of the resource IDs a billing activity query can be filtered by.

        Backed by ``billing_service_get_activity_filter_resource_names``. Only covers Studios,
        jobs, multi-machine jobs and deployments, ordered by resource ID.

        Args:
            org_id: ID of the organization to query.
            project_id: If given, restrict to resources in this teamspace (project).
            search_query: Only return resources whose name matches this.
            page_size: Maximum number of resources to return. The server defaults to 20.
            page_token: ``next_page_token`` from the previous page, to continue from it.

        Returns:
            BillingActivityResourceNames: The page of resource IDs.
        """
        kwargs: Dict[str, Any] = {"org_id": org_id}
        if project_id is not None:
            kwargs["project_id"] = project_id
        if search_query is not None:
            kwargs["search_query"] = search_query
        if page_size is not None:
            kwargs["page_size"] = page_size
        if page_token is not None:
            kwargs["page_token"] = page_token

        response = self._client.billing_service_get_activity_filter_resource_names(**kwargs)
        return BillingActivityResourceNames._from_api(response.to_dict())
