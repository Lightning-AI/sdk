from lightning_cloud.rest_client import LightningClient
from lightning_cloud.login import Auth
from lightning_cloud.openapi import V1GetUserResponse

from typing import Protocol, runtime_checkable


class UserApi:
    def __init__(self) -> None:
        super().__init__()

        self._client = LightningClient()

    def get_user(self, name: str) -> V1GetUserResponse:
        auth = Auth()
        auth.authenticate()
        user_id = auth.user_id
        user_name = auth.username
        res = self._client.auth_service_get_user()

        if not isinstance(res, V1GetUserResponse) or user_name != name:
            raise ValueError(f"User {name} does not exist")

        return res
