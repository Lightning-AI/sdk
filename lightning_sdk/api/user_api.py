from lightning_sdk.lightning_cloud.openapi import V1SearchUser
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class UserApi:
    """Internal API Client for user requests (mainly http requests)."""

    def __init__(self) -> None:
        super().__init__()

        self._client = LightningClient(max_tries=3)

    def get_user(self, name: str) -> V1SearchUser:
        """Gets user by name."""
        response = self._client.user_service_search_users(query=name)

        users = [u for u in response.users if u.username == name]
        if not len(users):
            raise ValueError(f"User {name} does not exist.")
        return users[0]

    def _get_user_by_id(self, user_id: str) -> V1SearchUser:
        response = self._client.user_service_search_users(query=user_id)
        users = [u for u in response.users if u.id == user_id]
        return users[0]
