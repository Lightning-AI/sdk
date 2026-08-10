from datetime import datetime
from typing import TYPE_CHECKING, Optional

from lightning_sdk.api import OrgApi
from lightning_sdk.api.org_api import MonthlySummary # noqa: F401
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
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[MonthlySummary]:
        """Returns a monthly summary of credits purchased, used, and remaining.

        Exactly one of ``start`` and ``end`` must be supplied,
        or both together:

        - only ``start``: grabs monthly summaries for months after ``pivot=start``.
        - only ``end``:  grabs monthly summaries for months before ``pivot=end``.
        - both ``start`` and ``end``: acts as a normal range.

        Args:
            start: Start of the time range. If given without
                ``end``, acts as an "AFTER" pivot.
            end: End of the time range. If given without
                ``start``, acts as a "BEFORE" pivot.

        Returns:
            A list of MonthlySummary dicts:
            [
                {
                    "period_start": datetime,
                    "period_end": datetime,
                    "total_credits_consumed": float,
                    "total_credits_remaining": float,
                    "total_credits_purchased": float,
                },
                ...
            ]

        Raises:
            ValueError: If neither ``start`` nor ``end`` is
                provided, if ``start`` is after ``end``, or if
                an "AFTER" pivot (derived from a lone ``start``) is in
                the future.
        """
        return self._org_api.get_monthly_summary(
            self.id,
            start=start,
            end=end,
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Organization(name={self.name})"
