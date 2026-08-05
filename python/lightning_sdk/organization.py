from datetime import datetime
from typing import TYPE_CHECKING, Optional

from lightning_sdk.api import OrgApi
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

    def get_monthly_summary(
        self,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
        pivot: Optional[datetime] = None,
        pivot_direction: Optional[str] = None,  # "BEFORE" | "AFTER"
    ) -> dict:
        """Returns a monthly summary of credits purchased, used, and remaining.
        
        Exactly one filter mode must be supplied:
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
        return self._org_api.get_monthly_summary(
            self.id,
            range_start=range_start,
            range_end=range_end,
            pivot=pivot,
            pivot_direction=pivot_direction,
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Organization(name={self.name})"
