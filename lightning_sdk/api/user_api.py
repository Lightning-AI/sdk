import re
from typing import Dict, List, Optional, Union

from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    SecretServiceUpdateUserSecretBody,
    V1CloudSpace,
    V1CreateProjectRequest,
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
        """Fetch a user by username, returning the authenticated user object if it matches.

        Args:
            name: The username to look up.

        Returns:
            Union[V1SearchUser, V1GetUserResponse]: The matching user record.

        Raises:
            ValueError: If no user with the given name exists.
        """
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
        """Look up a user by their unique ID.

        Args:
            user_id: The unique identifier of the user to look up.

        Returns:
            V1SearchUser: The matching user record.

        Raises:
            ValueError: If no user with the given ID exists.
        """
        response = self._client.user_service_search_users(query=user_id)
        users = [u for u in response.users if u.id == user_id]
        if not users:
            raise ValueError(f"User {user_id} does not exist.")
        return users[0]

    def _get_organizations_for_authed_user(
        self,
    ) -> List[V1Organization]:
        """Returns Organizations for the current authed user.

        Returns:
            List[V1Organization]: All organizations the authenticated user belongs to.
        """
        return self._client.organizations_service_list_organizations().organizations

    def _get_cloudspaces_for_user(self, project_id: str, user_id: str = "") -> List[V1CloudSpace]:
        """Return all Studios (cloud spaces) visible to a user within a project.

        Args:
            project_id: The ID of the project (teamspace) to list cloud spaces for.
            user_id: Optional user ID to filter cloud spaces by; defaults to all visible spaces.

        Returns:
            List[V1CloudSpace]: All cloud spaces visible within the given project.
        """
        resp: V1ListCloudSpacesResponse = self._client.cloud_space_service_list_cloud_spaces(
            project_id=project_id, user_id=user_id
        )
        return resp.cloudspaces

    def _get_all_teamspace_memberships(
        self,
        user_id: str,  # todo: this is unused, but still required
        org_id: Optional[str] = None,
    ) -> List[V1Membership]:
        """Return all teamspace memberships for the authenticated user, optionally scoped to an org.

        Args:
            user_id: The user ID (currently unused by the API but required by the signature).
            org_id: Optional organization ID to restrict memberships to a specific org.

        Returns:
            List[V1Membership]: All teamspace memberships for the authenticated user.
        """
        kwargs: Dict[str, Union[bool, str]] = {"filter_by_user_id": True}

        if org_id is not None:
            kwargs["organization_id"] = org_id

        return self._client.projects_service_list_memberships(**kwargs).memberships

    def _get_authed_user_name(self) -> str:
        """Gets the currently logged-in user.

        Returns:
            str: The username of the currently authenticated user.
        """
        auth = Auth()
        auth.authenticate()
        user = self._get_user_by_id(auth.user_id)
        return user.username

    def _get_feature_flags(self) -> V1UserFeatures:
        """Return the feature flags enabled for the authenticated user.

        Returns:
            V1UserFeatures: The feature-flag configuration for the authenticated user.
        """
        resp: V1GetUserResponse = self._client.auth_service_get_user()
        return resp.features

    def get_secrets(self) -> Dict[str, str]:
        """Get all secrets for the current user.

        Returns:
            Dict[str, str]: A mapping from secret name to a redacted placeholder value.
        """
        secrets = self._get_secrets()
        # this returns encrypted values for security. It doesn't make sense to show them,
        # so we just return a placeholder
        # not a security issue to replace in the client as we get the encrypted values from the server.
        return {secret.name: "***REDACTED***" for secret in secrets if secret.type == V1SecretType.UNSPECIFIED}

    def set_secret(self, key: str, value: str) -> None:
        """Create or replace an encrypted secret for the authenticated user.

        Args:
            key: The secret name.
            value: The plaintext secret value to store (encrypted at rest).
        """
        secrets = self._get_secrets()
        for secret in secrets:
            if secret.name == key:
                return self._update_secret(secret.id, value)
        return self._create_secret(key, value)

    def _get_secrets(self) -> List[V1Secret]:
        """Fetch all raw secret objects for the authenticated user.

        Returns:
            List[V1Secret]: All secrets belonging to the authenticated user.
        """
        return self._client.secret_service_list_user_secrets().secrets

    def _update_secret(self, secret_id: str, value: str) -> None:
        """Overwrite the value of an existing user secret by its ID.

        Args:
            secret_id: The unique ID of the secret to update.
            value: The new plaintext value to store for the secret.
        """
        self._client.secret_service_update_user_secret(
            body=SecretServiceUpdateUserSecretBody(value=value),
            id=secret_id,
        )

    def _create_secret(
        self,
        key: str,
        value: str,
    ) -> None:
        """Create a new encrypted secret for the authenticated user.

        Args:
            key: The name to assign to the new secret.
            value: The plaintext value to store (encrypted at rest).
        """
        self._client.secret_service_create_user_secret(body=V1CreateUserSecretRequest(name=key, value=value))

    def verify_secret_name(self, name: str) -> bool:
        """Check whether a secret name is valid.

        A valid name starts with a letter or underscore, followed only by letters, digits,
        or underscores.

        Args:
            name: The secret name to validate.

        Returns:
            bool: ``True`` if the name is valid, ``False`` otherwise.
        """
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        return re.match(pattern, name) is not None

    def create_teamspace(self, name: str) -> None:
        """Create a new teamspace owned by the authenticated user.

        Args:
            name: The display name for the new teamspace.
        """
        self._client.projects_service_create_project(body=V1CreateProjectRequest(name=name, display_name=name))
