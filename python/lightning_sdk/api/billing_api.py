"""Low-level client and response types for the billing/usage-report endpoints.

:class:`BillingApi` wraps both the generated OpenAPI client (for the JSON usage report and
filter-values endpoints) and hand-rolled authenticated HTTP requests (for the CSV download
endpoints, which aren't exposed by the generated client). The ``lightning_sdk.billing`` module
provides the higher-level, user-facing interface built on top of this one.

Three ways to get billing activity, at different grains:
    - :meth:`BillingApi.get_activity`: paginated, per-resource-per-day rollup rows with raw IDs
      (no resolved names). Meant for programmatic/incremental consumption.
    - :meth:`BillingApi.get_session_activity`: one row per session, with resolved names. A
      resource (e.g. a Studio or Job) can have many sessions in the queried range. Returns CSV
      or JSON depending on the ``format`` argument.
    - :meth:`BillingApi.get_resource_activity`: one row per resource that was active in the
      queried range, with resolved names, a more concise view than the session-level report.
      Returns CSV or JSON depending on the ``format`` argument.
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
        resource_type: Type of the resource (e.g. "Studio", "Job").
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
    """A filterable resource ID paired with its display name.

    Attributes:
        id: ID of the resource.
        name: Display name of the resource.
    """

    id: Optional[str] = None
    name: Optional[str] = None

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingNamedFilterValue":
        return cls(id=data.get("id"), name=data.get("name"))


@dataclass
class BillingActivityFilterValues:
    """The set of values a billing activity query can be filtered by, for a given scope.

    Attributes:
        project_ids: Teamspace (project) IDs with billing activity in the queried scope.
        resource_ids: Resource IDs with billing activity in the queried scope, paired with
            their display names.
        resource_ids_truncated: Whether ``resource_ids`` was truncated due to too many results.
        resource_types: Resource types with billing activity in the queried scope.
        user_ids: User IDs with billing activity in the queried scope.
    """

    project_ids: List[str] = field(default_factory=list)
    resource_ids: List[BillingNamedFilterValue] = field(default_factory=list)
    resource_ids_truncated: bool = False
    resource_types: List[str] = field(default_factory=list)
    user_ids: List[str] = field(default_factory=list)

    @classmethod
    def _from_api(cls, data: Dict[str, Any]) -> "BillingActivityFilterValues":
        return cls(
            project_ids=list(data.get("project_ids") or []),
            resource_ids=[BillingNamedFilterValue._from_api(item) for item in data.get("resource_ids") or []],
            resource_ids_truncated=bool(data.get("resource_ids_truncated")),
            resource_types=list(data.get("resource_types") or []),
            user_ids=list(data.get("user_ids") or []),
        )


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
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: Optional[int] = None,
    search_after: Optional[datetime] = None,
    search_after_resource_id: Optional[str] = None,
    search_after_resource_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the query params shared by the V2 usage report and its CSV download endpoints."""
    query_params: Dict[str, Any] = {"orgId": org_id}
    if project_ids is not None:
        query_params["projectIds"] = project_ids
    if resource_types is not None:
        query_params["resourceTypes"] = resource_types
    if resource_ids is not None:
        query_params["resourceIds"] = resource_ids
    if user_ids is not None:
        query_params["userIds"] = user_ids
    if start is not None:
        query_params["from"] = start.isoformat()
    if end is not None:
        query_params["to"] = end.isoformat()
    if limit is not None:
        query_params["limit"] = limit
    if search_after is not None:
        query_params["searchAfter"] = search_after.isoformat()
    if search_after_resource_id is not None:
        query_params["searchAfterResourceId"] = search_after_resource_id
    if search_after_resource_type is not None:
        query_params["searchAfterResourceType"] = search_after_resource_type
    return query_params


class BillingApi:
    """Internal API client for billing/usage-report requests.

    Combines calls through the generated OpenAPI client (:meth:`get_activity`,
    :meth:`get_activity_filter_values`) with raw authenticated HTTP requests for the CSV
    download endpoints (:meth:`get_session_activity`, :meth:`get_resource_activity`), which
    aren't exposed by the generated client. Both return CSV or JSON depending on the ``format``
    argument; the JSON variant is built on top of the CSV download, converting it in memory.
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
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
        search_after_resource_id: Optional[str] = None,
        search_after_resource_type: Optional[str] = None,
    ) -> str:
        """Download a billing activity report and return its raw CSV text."""
        query_params = _build_activity_query_params(
            org_id=org_id,
            project_ids=project_ids,
            resource_types=resource_types,
            resource_ids=resource_ids,
            user_ids=user_ids,
            start=start,
            end=end,
            limit=limit,
            search_after=search_after,
            search_after_resource_id=search_after_resource_id,
            search_after_resource_type=search_after_resource_type,
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
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
        search_after_resource_id: Optional[str] = None,
        search_after_resource_type: Optional[str] = None,
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
            start=start,
            end=end,
            limit=limit,
            search_after=search_after,
            search_after_resource_id=search_after_resource_id,
            search_after_resource_type=search_after_resource_type,
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
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
        search_after_resource_id: Optional[str] = None,
        search_after_resource_type: Optional[str] = None,
    ) -> None:
        """Get the session-level billing activity report, as CSV or JSON.

        One row per session. A resource (e.g. a Studio or Job) can have many sessions within
        the queried time range, so this report is the finer-grained of the two; use
        :meth:`get_resource_activity` for one row per resource instead.

        Hits ``GET /v1/billing/usage-report/download/detailed`` with the same request shape as
        the V2 usage report (see :meth:`get_activity`). Not exposed by the generated OpenAPI
        client, so this issues a raw authenticated HTTP request directly against ``self._client``'s
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
            start=start,
            end=end,
            limit=limit,
            search_after=search_after,
            search_after_resource_id=search_after_resource_id,
            search_after_resource_type=search_after_resource_type,
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
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
        search_after_resource_id: Optional[str] = None,
        search_after_resource_type: Optional[str] = None,
    ) -> None:
        """Get the resource-level billing activity report, as CSV or JSON.

        One row per resource (e.g. a Studio or Job) that was active in the queried time range,
        rather than one row per session; use :meth:`get_session_activity` for the
        finer-grained, per-session breakdown of a resource's activity.

        Hits ``GET /v1/billing/usage-report/download/summary`` with the same request shape as
        the V2 usage report (see :meth:`get_activity`). Not exposed by the generated OpenAPI
        client, so this issues a raw authenticated HTTP request directly against ``self._client``'s
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
            start=start,
            end=end,
            limit=limit,
            search_after=search_after,
            search_after_resource_id=search_after_resource_id,
            search_after_resource_type=search_after_resource_type,
        )

    def get_activity(
        self,
        org_id: str,
        project_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
        search_after_resource_id: Optional[str] = None,
        search_after_resource_type: Optional[str] = None,
    ) -> BillingActivity:
        """Get billing activity for an organization, optionally scoped to specific teamspaces.

        Returns paginated, per-resource-per-day rollup rows keyed by raw IDs (no resolved
        names); backed by the daily rollup billing activity endpoint. For a resolved-name, non-paginated
        report meant for reading or exporting, use :meth:`get_session_activity` (one row
        per session) or :meth:`get_resource_activity` (one row per resource) instead.

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
        resource types, and resource IDs available to filter the activity page by, for the given
        scope.

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
