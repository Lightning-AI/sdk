from typing import Optional

from lightning_sdk.api import UserApi
from lightning_sdk.owner import Owner
from lightning_sdk.utils.resolve import _resolve_user_name


class User(Owner):
    """Represents a user owner of teamspaces and studios.

    Args:
        name: the name of the user

    Note:
        Arguments will be automatically inferred from environment variables if possible,
        unless explicitly specified

    """

    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__()
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

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"User(name={self.name})"
