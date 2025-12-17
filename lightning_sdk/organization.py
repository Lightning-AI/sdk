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
        return self._org.preferred_cluster or None

    def create_teamspace(self, name: str) -> "Teamspace":
        from lightning_sdk.teamspace import Teamspace

        self._org_api.create_teamspace(name, self.id)
        return Teamspace(name=name, org=self)

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Organization(name={self.name})"
