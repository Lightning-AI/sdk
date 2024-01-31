from typing import TYPE_CHECKING, List, Optional

from lightning_sdk.api import TeamspaceApi, UserApi
from lightning_sdk.utils import _resolve_user_name

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


class User:
    """Represents a user owner of teamspaces and studios.

    Args:
        name: the name of the user

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
        self._teamspace_api = TeamspaceApi()
        self._user_api = UserApi()

        name = _resolve_user_name(name)
        if name is None:
            raise ValueError("Neither name is provided nor can the user be inferred from the environment variable!")

        self._user = self._user_api.get_user(name=name)

    @property
    def name(self) -> str:
        """The user's name."""
        return self._user.username

    @property
    def id(self) -> str:
        """The user's ID."""
        return self._user.id

    @property
    def teamspaces(self) -> List["Teamspace"]:
        """All teamspaces by this user."""
        from lightning_sdk.teamspace import Teamspace

        _teamspaces = self._teamspace_api.list_teamspaces(owner_id=self.id, name=None)
        return [Teamspace(name=t.name, org=self) for t in _teamspaces]
