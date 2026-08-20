"""Shared types and request-building for the billing activity report.

Backs both org-scoped (:class:`~lightning_sdk.api.org_api.OrgApi`) and
teamspace-scoped (:class:`~lightning_sdk.api.teamspace_api.TeamspaceApi`) callers of the
``GetRollupUsageReport`` endpoint.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict


class UsageActivity(TypedDict):
    """A single resource's billing activity, as returned by the usage report.

    Attributes:
        id: ID of the resource (e.g. studio, job) this usage session belongs to.
        name: Display name of the resource.
        resource_type: Type of the resource (e.g. ``"studio"``, ``"job"``).
        user_id: ID of the user who owns/ran the resource.
        cluster_id: ID of the cloud account the resource ran on.
        created_at: When the resource was created.
        deleted_at: When the resource was deleted, if applicable.
        session_started_at: When this usage session started.
        session_ended_at: When this usage session ended, if it has.
        billed_time_seconds: Total billed time for the session, in seconds.
        cost: Total credits spent during the session.
        saved_cost: Total credits saved during the session (e.g. via spot pricing).
        project_id: ID of the teamspace the resource belongs to.
        free: Whether the session was/is free.
        spot: Whether the session ran on a spot instance.
        instance_type: The instance type used, if applicable (e.g. for reservations).
        total_prompt_tokens: Total prompt tokens consumed, for LLM-backed resources.
        total_completion_tokens: Total completion tokens consumed, for LLM-backed resources.
        total_num_messages: Total number of messages, for LLM-backed resources.
    """

    id: str
    name: str
    resource_type: str
    user_id: str
    cluster_id: str
    created_at: Optional[datetime]
    deleted_at: Optional[datetime]
    session_started_at: Optional[datetime]
    session_ended_at: Optional[datetime]
    billed_time_seconds: int
    cost: float
    saved_cost: float
    project_id: str
    free: bool
    spot: bool
    instance_type: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_num_messages: int


class DailyUsageActivity(TypedDict):
    """A single day's aggregated billing activity.

    Attributes:
        day: The day this aggregate covers.
        total_cost: Total credits spent across all resources on this day.
        total_prompt_tokens: Total prompt tokens consumed on this day.
        total_completion_tokens: Total completion tokens consumed on this day.
        total_num_messages: Total number of messages on this day.
    """

    day: datetime
    total_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_num_messages: int


class BillingActivityReport(TypedDict):
    """The daily-rollup billing activity report for an org or teamspace.

    Attributes:
        total_cost: Total credits spent by all filtered resources in the queried time range.
        total_saved_cost: Total credits saved by all filtered resources in the queried time range.
        total_users: Total distinct users across all filtered resources in the queried time range.
        usage: Per-resource usage sessions matching the filters.
        daily_usage: Per-day aggregated usage matching the filters.
        has_more: Whether more entries exist past ``limit``.
        search_after: Cursor to pass as ``search_after`` to fetch the next page, if ``has_more``.
    """

    total_cost: float
    total_saved_cost: float
    total_users: int
    usage: List[UsageActivity]
    daily_usage: List[DailyUsageActivity]
    has_more: bool
    search_after: Optional[datetime]


def _build_rollup_usage_report_kwargs(
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    cluster_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: Optional[int] = None,
    search_after: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build the kwargs for ``billing_service_get_rollup_usage_report``, omitting unset filters."""
    kwargs: Dict[str, Any] = {}
    if org_id is not None:
        kwargs["org_id"] = org_id
    if project_id is not None:
        kwargs["project_id"] = project_id
    if start is not None:
        kwargs["_from"] = start
    if end is not None:
        kwargs["to"] = end
    if cluster_id is not None:
        kwargs["cluster_id"] = cluster_id
    if resource_type is not None:
        kwargs["resource_type"] = resource_type
    if resource_id is not None:
        kwargs["resource_id"] = resource_id
    if user_id is not None:
        kwargs["user_id"] = user_id
    if limit is not None:
        kwargs["limit"] = limit
    if search_after is not None:
        kwargs["search_after"] = search_after
    return kwargs
