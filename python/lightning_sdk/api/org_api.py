from datetime import datetime, timedelta
import typing
from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import (
    V1CreateProjectRequest,
    V1Organization,
)

# The billing summary API only supports querying up to 2 years of history.
_MAX_DURATION = timedelta(days=730)

class OrgApi:
    """Internal API client for org requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = cached_lightning_client()

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
        range_start: typing.Optional[datetime] = None,
        range_end: typing.Optional[datetime] = None,
        pivot: typing.Optional[datetime] = None,
        pivot_direction: typing.Optional[str] = None,  # "BEFORE" | "AFTER"
    ) -> dict:
        """Get the monthly billing summary of an organization.

        Exactly one filter mode must be supplied (the API rejects a missing or
        empty TimeFilter):
        - a range: pass both ``range_start`` and ``range_end``
        - a pivot: pass ``pivot`` and ``pivot_direction`` ("BEFORE" or "AFTER")

        Args:
            organization_id: ID of the organization to summarize.
            range_start: Start of the time range (use with ``range_end``).
            range_end: End of the time range (use with ``range_start``).
            pivot: Pivot timestamp (use with ``pivot_direction``).
            pivot_direction: "BEFORE" or "AFTER" the pivot.

        Returns:
            dict: The monthly summary as a plain dictionary.

        Raises:
            ValueError: If not exactly one valid filter mode is provided, if the
                range start is after the range end, or if an "AFTER" pivot is in
                the future.
        """
        has_range = range_start is not None and range_end is not None
        has_pivot = pivot is not None and pivot_direction is not None

        if has_range == has_pivot:
            raise ValueError("Provide exactly one of a time range or a pivot, not both/neither.")

        kwargs = {"org_id": organization_id}

        if has_range:
            if range_start > range_end:
                raise ValueError("range_start must not be after range_end.")
            if range_end - range_start > _MAX_DURATION:
                raise ValueError("the time range must not be longer than 2 years.")
            kwargs["time_filter_range_filter_range_start"] = range_start
            kwargs["time_filter_range_filter_range_end"] = range_end
        else:
            if pivot_direction not in ("BEFORE", "AFTER"):
                raise ValueError('pivot_direction must be "BEFORE" or "AFTER".')
            if pivot_direction == "AFTER":
                # An "AFTER" pivot selects [pivot, now]; it must be in the past
                # and no more than 2 years back.
                now = datetime.now(pivot.tzinfo) if pivot.tzinfo is not None else datetime.now()
                if pivot > now:
                    raise ValueError("pivot must not be in the future when pivot_direction is AFTER.")
                if now - pivot > _MAX_DURATION:
                    raise ValueError("an AFTER pivot must not be more than 2 years in the past.")
            kwargs["time_filter_pivot_filter_pivot"] = pivot
            kwargs["time_filter_pivot_filter_pivot_direction"] = pivot_direction

        return self._client.billing_service_get_monthly_summary(**kwargs).to_dict()
