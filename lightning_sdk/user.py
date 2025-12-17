from typing import TYPE_CHECKING, Dict, List, Optional

from lightning_sdk.api import UserApi
from lightning_sdk.owner import Owner
from lightning_sdk.utils.resolve import _get_authed_user, _get_organizations_for_authed_user, _resolve_user_name

if TYPE_CHECKING:
    from lightning_sdk.organization import Organization
    from lightning_sdk.teamspace import Teamspace


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

    @property
    def secrets(self) -> Dict[str, str]:
        """All (encrypted) secrets for the user.

        Note:
            Once created, the secret values are encrypted and cannot be viewed here anymore.
        """
        return self._user_api.get_secrets()

    def set_secret(self, key: str, value: str) -> None:
        """Set a (encrypted) secret for the user."""
        if not self._user_api.verify_secret_name(key):
            raise ValueError(
                "Secret keys must only contain alphanumeric characters and underscores and not begin with a number."
            )

        self._user_api.set_secret(key, value)

    def create_teamspace(self, name: str) -> "Teamspace":
        from lightning_sdk.teamspace import Teamspace

        if not _get_authed_user().id == self.id:
            raise ValueError("Can only create teamspaces for currently authenticated user")

        self._user_api.create_teamspace(name)
        return Teamspace(name=name, user=self)

    @property
    def organizations(self) -> List["Organization"]:
        if not _get_authed_user().id == self.id:
            raise ValueError("Can only list organizations for currently authenticated user")

        return _get_organizations_for_authed_user(user_api=self._user_api)

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"User(name={self.name})"
