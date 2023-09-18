from typing import Protocol, runtime_checkable

from lightning_cloud.login import Auth
from lightning_cloud.openapi import UserServiceApi, V1SearchUser
from lightning_cloud.rest_client import LightningClient


class UserApi:
    """Internal API Client for user requests (mainly http requests)"""

    def __init__(self) -> None:
        super().__init__()

        # TODO: add user service to lightning client
        self._client = UserServiceApi(api_client=LightningClient().api_client)

    def get_user(self, name: str) -> V1SearchUser:
        """Gets user by name"""
        response = self._client.user_service_search_users(query=name)

        users = [u for u in response.users if u.username == name]
        if not len(users):
            raise ValueError(f"User {name} does not exist.")
        user = users[0]
        return user

    def _get_user_by_id(self, id: str) -> V1SearchUser:
        response = self._client.user_service_search_users(query=id)
        users = [u for u in response.users if u.id == id]
        user = users[0]
        assert user.id == id
        return user
