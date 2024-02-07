from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from lightning_sdk.api import TeamspaceApi

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


class Owner(ABC):
    """Represents an owner of teamspaces and studios."""

    def __init__(self) -> None:
        self._teamspace_api = TeamspaceApi()

    @property
    @abstractmethod
    def name(self) -> str:
        """The owner's name."""

    @property
    @abstractmethod
    def id(self) -> str:
        """The owner's ID."""

    @property
    def teamspaces(self) -> List["Teamspace"]:
        """All teamspaces by this owner."""
        from lightning_sdk.teamspace import Teamspace
        from lightning_sdk.user import User

        is_user = isinstance(self, User)
        if is_user:
            user = self
            org = None
        else:
            user = None
            org = self

        _teamspaces = self._teamspace_api.list_teamspaces(owner_id=self.id, name=None)
        return [Teamspace(name=t.name, user=user, org=org) for t in _teamspaces]

    def __eq__(self, o: "Owner") -> bool:
        """Checks for equality with provided object."""
        return type(o) is type(self) and self.id == o.id and self.name == o.name

    def __str__(self) -> str:
        """Returns reader friendly representation."""
        return repr(self)
