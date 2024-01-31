from typing import TYPE_CHECKING, List, Optional

from lightning_sdk.api import OrgApi, TeamspaceApi
from lightning_sdk.utils import _resolve_org_name

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


class Organization:
    """Represents an organization owner of teamspaces and studios.

    Args:
        name: the name of the organization

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
        self._teamspace_api = TeamspaceApi()
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
    def teamspaces(self) -> List["Teamspace"]:
        """All teamspaces by this user."""
        from lightning_sdk.teamspace import Teamspace

        _teamspaces = self._teamspace_api.list_teamspaces(owner_id=self.id, name=None)
        return [Teamspace(name=t.name, org=self) for t in _teamspaces]
