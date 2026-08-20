from datetime import datetime
from typing import Optional

from lightning_sdk.api.billing_activity import BillingActivityReport, _build_rollup_usage_report_kwargs
from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import (
    V1CreateProjectRequest,
    V1Organization,
)


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

    def get_billing_activity(
        self,
        organization_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        cluster_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
    ) -> BillingActivityReport:
        """Get the daily-rollup billing activity across all of an organization's teamspaces.

        # TODO(billing-revamp-sdk): stub — wire up pagination (has_more/search_after) and
        # decide on the public, front-facing shape once the backend endpoint has settled.

        Args:
            organization_id: ID of the organization to report on.
            start: Start of the time range. If omitted, defaults to the resource creation time.
            end: End of the time range. If omitted, defaults to the resource deletion time or now.
            cluster_id: Restrict to a single cloud account. If omitted, all clusters are included.
            resource_type: Restrict to a single resource type (e.g. ``"studio"``, ``"job"``).
                If omitted, all resource types are included.
            resource_id: Restrict to a single resource. If omitted, all matching resources
                are included.
            user_id: Restrict to a single user's activity. If omitted, all users are included.
            limit: Max number of usage entries to return.
            search_after: Only include usage entries strictly after this cursor
                (the ``search_after`` from a previous, paginated call).

        Returns:
            A BillingActivityReport with per-resource and per-day usage plus totals,
            aggregated across every teamspace in the organization.
        """
        kwargs = _build_rollup_usage_report_kwargs(
            org_id=organization_id,
            start=start,
            end=end,
            cluster_id=cluster_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            limit=limit,
            search_after=search_after,
        )
        return self._client.billing_service_get_rollup_usage_report(**kwargs).to_dict()
