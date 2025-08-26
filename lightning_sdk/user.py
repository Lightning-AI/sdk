from typing import Dict, Optional

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

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"User(name={self.name})"
