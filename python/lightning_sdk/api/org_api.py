from typing import List, Optional, TypedDict
from datetime import datetime, timedelta

from lightning_sdk.lightning_cloud.openapi import (
    V1CreateProjectRequest,
    V1Organization,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient

# The billing summary API only supports querying up to 2 years of history.
_MAX_DURATION = timedelta(days=730)


class MonthlySummary(TypedDict):
    period_start: datetime
    period_end: datetime
    total_credits_consumed: float
    total_credits_remaining: float
    total_credits_purchased: float


class MonthlySummaryResponse(TypedDict):
    org_id: str
    monthly_summaries: List[MonthlySummary]


class OrgApi:
    """Internal API client for org requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_org(self, name: str) -> V1Organization:
        """Fetch an organisation by name.

        Args:
            name: The organisation name to look up.

        Returns:
            V1Organization: The matching organisation record.

        Raises:
            ValueError: If no organisation with the given name exists.
        """
        res = self._client.organizations_service_get_organization(id="", name=name)
        if not res:
            raise ValueError(f"Org {name} does not exist")
        return res

    def _get_org_by_id(self, org_id: str) -> V1Organization:
        """Gets the organization from the given ID.

        Args:
            org_id: The unique ID of the organisation to retrieve.

        Returns:
            V1Organization: The matching organisation record.
        """
        return self._client.organizations_service_get_organization(id=org_id)

    def create_teamspace(self, name: str, organization_id: str) -> None:
        """Create a new teamspace owned by the given organisation.

        Args:
            name: The display name for the new teamspace.
            organization_id: The ID of the owning organisation.
        """
        self._client.projects_service_create_project(
            body=V1CreateProjectRequest(name=name, organization_id=organization_id, display_name=name)
        )

    def get_monthly_summary(
        self,
        organization_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> MonthlySummaryResponse:
        """Get the monthly billing summary of an organization.

        Exactly one of ``start`` and ``end`` must be supplied,
        or both together:
        - only ``start``: translated to a pivot filter with
          ``pivot_direction="AFTER"`` and ``pivot=start``.
        - only ``end``: translated to a pivot filter with
          ``pivot_direction="BEFORE"`` and ``pivot=end``.
        - both ``start`` and ``end``: translated to a normal
          range filter.

        Args:
            organization_id: ID of the organization to summarize.
            start: Start of the time range. If given without
                ``end``, acts as an "AFTER" pivot.
            end: End of the time range. If given without
                ``start``, acts as a "BEFORE" pivot.

        Returns:
            MonthlySummaryResponse: A dict with the following shape:
            {
                "org_id": str,
                "monthly_summaries": [
                    {
                        "period_start": datetime,
                        "period_end": datetime,
                        "total_credits_consumed": float,
                        "total_credits_remaining": float,
                        "total_credits_purchased": float,
                    },
                    ...
                ],
            }

        Raises:
            ValueError: If neither ``start`` nor ``end`` is
                provided, if ``start`` is after ``end``, or if
                an "AFTER" pivot (derived from a lone ``start``) is in
                the future.
        """
        if start is None and end is None:
            raise ValueError("Provide at least one of start or end.")

        kwargs = {"org_id": organization_id}

        if start is not None and end is not None:
            if start > end:
                raise ValueError("start must not be after end.")
            if end - start > _MAX_DURATION:
                raise ValueError("the time range must not be longer than 2 years.")
            kwargs["time_filter_range_filter_range_start"] = start
            kwargs["time_filter_range_filter_range_end"] = end
        elif start is not None:
            pivot = start
            # An "AFTER" pivot selects [pivot, now]; it must be in the past
            # and no more than 2 years back.
            now = datetime.now(pivot.tzinfo) if pivot.tzinfo is not None else datetime.now()
            if pivot > now:
                raise ValueError("start must not be in the future.")
            if now - pivot > _MAX_DURATION:
                raise ValueError("start must not be more than 2 years in the past.")
            kwargs["time_filter_pivot_filter_pivot"] = pivot
            kwargs["time_filter_pivot_filter_pivot_direction"] = "AFTER"
        else:
            kwargs["time_filter_pivot_filter_pivot"] = end
            kwargs["time_filter_pivot_filter_pivot_direction"] = "BEFORE"

        return self._client.billing_service_get_monthly_summary(**kwargs).to_dict()
