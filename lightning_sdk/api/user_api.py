from typing import List

from lightning_sdk.lightning_cloud.openapi import (
    V1CloudSpace,
    V1ListCloudSpacesResponse,
    V1Membership,
    V1Organization,
    V1SearchUser,
)
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

    def _get_organizations_for_authed_user(
        self,
    ) -> List[V1Organization]:
        """Returns Organizations for the current authed user."""
        return self._client.organizations_service_list_organizations().organizations

    def _get_cloudspaces_for_user(self, user_id: str, project_id: str) -> List[V1CloudSpace]:
        resp: V1ListCloudSpacesResponse = self._client.cloud_space_service_list_cloud_spaces(
            project_id=project_id, user_id=user_id
        )
        return resp.cloudspaces

    def _get_all_teamspace_memberships(self, user_id: str) -> List[V1Membership]:
        return self._client.projects_service_list_memberships(filter_by_user_id=True).memberships
