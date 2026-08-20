from datetime import datetime
from typing import TYPE_CHECKING, Optional

from lightning_sdk.api import OrgApi
from lightning_sdk.api.billing_activity import BillingActivityReport
from lightning_sdk.owner import Owner
from lightning_sdk.utils.resolve import _resolve_org_name

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


class Organization(Owner):
    """Represents an organization owner of teamspaces and studios.

    Args:
        name: the name of the organization

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
        self._org_api = OrgApi()
        if name is None:
            name = _resolve_org_name(name)

        if name is None:
            raise ValueError(
                "Neither name is provided nor can the organization be inferred from the environment variable!"
            )

        self._org = self._org_api.get_org(name=name)

    @property
    def name(self) -> str:
        """The organization's name."""
        return self._org.name

    @property
    def id(self) -> str:
        """The organization's ID."""
        return self._org.id

    @property
    def default_cloud_account(self) -> Optional[str]:
        """The organization's preferred cloud account ID, or None if not set.

        Returns:
            str | None: The preferred cloud account ID.
        """
        return self._org.preferred_cluster or None

    def create_teamspace(self, name: str) -> "Teamspace":
        """Create a new teamspace owned by this organization.

        Args:
            name: The name for the new teamspace.

        Returns:
            Teamspace: The newly created teamspace.
        """
        from lightning_sdk.teamspace import Teamspace

        self._org_api.create_teamspace(name, self.id)
        return Teamspace(name=name, org=self)

    def get_billing_activity(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        cluster_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        search_after: Optional[datetime] = None,
    ) -> BillingActivityReport:
        """Get the daily-rollup billing activity across all of this organization's teamspaces.

        Args:
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
            A :class:`~lightning_sdk.api.billing_activity.BillingActivityReport` with
            per-resource and per-day usage plus totals, aggregated across every teamspace
            in the organization.
        """
        return self._org_api.get_billing_activity(
            self.id,
            start=start,
            end=end,
            cluster_id=cluster_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            limit=limit,
            search_after=search_after,
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Organization(name={self.name})"
