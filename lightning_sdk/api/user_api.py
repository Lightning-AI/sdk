import re
from typing import Dict, List, Union

from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    SecretsIdBody1,
    V1CloudSpace,
    V1CreateUserSecretRequest,
    V1GetUserResponse,
    V1ListCloudSpacesResponse,
    V1Membership,
    V1Organization,
    V1SearchUser,
    V1Secret,
    V1UserFeatures,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_secret_type import V1SecretType
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class UserApi:
    """Internal API Client for user requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_user(self, name: str) -> Union[V1SearchUser, V1GetUserResponse]:
        """Gets user by name."""
        authed_user = self._client.auth_service_get_user()
        if authed_user.username == name:
            return authed_user

        # if it's not the authed user, lookup by name
        # TODO: This API won't necesarily return the correct thing
        response = self._client.user_service_search_users(query=name)

        users = [u for u in response.users if u.username == name]
        if not users:
            raise ValueError(f"User {name} does not exist.")
        return users[0]

    def _get_user_by_id(self, user_id: str) -> V1SearchUser:
        response = self._client.user_service_search_users(query=user_id)
        users = [u for u in response.users if u.id == user_id]
        if not users:
            raise ValueError(f"User {user_id} does not exist.")
        return users[0]

    def _get_organizations_for_authed_user(
        self,
    ) -> List[V1Organization]:
        """Returns Organizations for the current authed user."""
        return self._client.organizations_service_list_organizations().organizations

    def _get_cloudspaces_for_user(self, project_id: str, user_id: str = "") -> List[V1CloudSpace]:
        resp: V1ListCloudSpacesResponse = self._client.cloud_space_service_list_cloud_spaces(
            project_id=project_id, user_id=user_id
        )
        return resp.cloudspaces

    def _get_all_teamspace_memberships(
        self,
        user_id: str,  # todo: this is unused, but still required
    ) -> List[V1Membership]:
        return self._client.projects_service_list_memberships(filter_by_user_id=True).memberships

    def _get_authed_user_name(self) -> str:
        """Gets the currently logged-in user."""
        auth = Auth()
        auth.authenticate()
        user = self._get_user_by_id(auth.user_id)
        return user.username

    def _get_feature_flags(self) -> V1UserFeatures:
        resp: V1GetUserResponse = self._client.auth_service_get_user()
        return resp.features

    def get_secrets(self) -> Dict[str, str]:
        """Get all secrets for the current user."""
        secrets = self._get_secrets()
        # this returns encrypted values for security. It doesn't make sense to show them,
        # so we just return a placeholder
        # not a security issue to replace in the client as we get the encrypted values from the server.
        return {secret.name: "***REDACTED***" for secret in secrets if secret.type == V1SecretType.UNSPECIFIED}

    def set_secret(self, key: str, value: str) -> None:
        """Set a secret for the current user.

        This will replace the existing secret if it exists and create a new one if it doesn't.
        """
        secrets = self._get_secrets()
        for secret in secrets:
            if secret.name == key:
                return self._update_secret(secret.id, value)
        return self._create_secret(key, value)

    def _get_secrets(self) -> List[V1Secret]:
        return self._client.secret_service_list_user_secrets().secrets

    def _update_secret(self, secret_id: str, value: str) -> None:
        self._client.secret_service_update_user_secret(
            body=SecretsIdBody1(value=value),
            id=secret_id,
        )

    def _create_secret(
        self,
        key: str,
        value: str,
    ) -> None:
        self._client.secret_service_create_user_secret(body=V1CreateUserSecretRequest(name=key, value=value))

    def verify_secret_name(self, name: str) -> bool:
        """Verify if a secret name is valid.

        A valid secret name starts with a letter or underscore, followed by letters, digits, or underscores.
        """
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        return re.match(pattern, name) is not None
