from typing import TYPE_CHECKING, Optional

from lightning_sdk.lightning_cloud.openapi import V1APIKey, V1CreateAPIKeyRequest
from lightning_sdk.lightning_cloud.rest_client import LightningClient

if TYPE_CHECKING:
    from lightning_sdk.organization import Organization

_DEFAULT_KEY_NAME = "Default"
_DEFAULT_KEY_DESCRIPTION = "Auto-created for model API access"


class ApiKeyApi:
    """API client for org-scoped API keys used with public model endpoints."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def _try_resolve_org_by_name(self, name: Optional[str]) -> Optional["Organization"]:
        if not name:
            return None

        from lightning_sdk.utils.resolve import _resolve_org

        try:
            return _resolve_org(name)
        except ValueError:
            return None

    def resolve_org_context(self, org_name: Optional[str] = None) -> Optional["Organization"]:
        """Resolve the org context for model API keys, mirroring the UI home-org behavior.

        Resolution order:
        1. Explicit ``org_name``, ``LIGHTNING_ORG``, or configured ``organization.name``
        2. The authenticated user's default organization
        3. The first organization returned for the user

        If you belong to multiple orgs, set ``LIGHTNING_ORG`` or
        ``organization.name`` in ``~/.lightning/config.yaml`` to match the org
        selected in the web UI. The UI tracks home org in browser session storage,
        which the CLI does not read.
        """
        from lightning_sdk.utils.resolve import _resolve_org_name

        configured_name = _resolve_org_name(org_name)
        if configured_name:
            org = self._try_resolve_org_by_name(configured_name)
            if org is None:
                raise ValueError(f"Organization '{configured_name}' does not exist or you are not a member of it.")
            return org

        user = self._client.auth_service_get_user()
        org = self._try_resolve_org_by_name(user.organization)
        if org is not None:
            return org

        embedded_orgs = user.organizations or []
        for candidate in embedded_orgs:
            org = self._try_resolve_org_by_name(candidate.name)
            if org is not None:
                return org

        listed_orgs = self._client.organizations_service_list_organizations().organizations or []
        for candidate in listed_orgs:
            org = self._try_resolve_org_by_name(candidate.name)
            if org is not None:
                return org

        return None

    def _get_authed_user_id(self) -> str:
        user = self._client.auth_service_get_user()
        if not user.id:
            raise RuntimeError("Unable to determine the authenticated user.")
        return user.id

    def _find_member_role_id(self, org_id: str) -> str:
        roles = self._client.organizations_service_list_org_roles(org_id=org_id).roles or []
        member_role = next((role for role in roles if "member" in (role.name or "").lower()), None)
        if member_role is None or not member_role.id:
            raise RuntimeError(f"No member role found for organization {org_id}.")
        return member_role.id

    def create(
        self,
        org_id: str,
        name: str,
        *,
        role_id: Optional[str] = None,
        description: str = "",
    ) -> V1APIKey:
        """Create an org-scoped API key.

        Args:
            org_id: Organization ID the key belongs to.
            name: Display name for the key.
            role_id: Role ID to assign. Defaults to the org's member role.
            description: Optional description for the key.

        Returns:
            V1APIKey: The created key, including ``raw_key`` once at creation time.
        """
        if not description and name == _DEFAULT_KEY_NAME:
            description = _DEFAULT_KEY_DESCRIPTION
        resolved_role_id = role_id or self._find_member_role_id(org_id)
        return self._client.projects_service_create_api_key(
            body=V1CreateAPIKeyRequest(
                org_id=org_id,
                name=name,
                description=description,
                role=resolved_role_id,
            )
        )

    def list(self, org_id: str, *, mine_only: bool = True) -> list[V1APIKey]:
        """List API keys for an organization.

        Args:
            org_id: Organization ID to list keys for.
            mine_only: When True, return only keys created by the current user.

        Returns:
            list[V1APIKey]: Matching API keys.
        """
        response = self._client.projects_service_list_api_keys(org_id=org_id)
        keys = response.api_keys or []
        if not mine_only:
            return keys

        user_id = self._get_authed_user_id()
        return [key for key in keys if key.creator_id == user_id]

    def delete(self, org_id: str, key_id: str) -> None:
        """Delete an org-scoped API key."""
        self._client.projects_service_delete_api_key(id=key_id, org_id=org_id)

    def get_personal_api_key(self) -> str:
        """Return the authenticated user's global platform API key."""
        user = self._client.auth_service_get_user()
        if not user.api_key:
            raise RuntimeError(
                "No personal API key found. Run `lightning login` or create an org key with "
                "`lightning api-key create --org <org>`."
            )
        return user.api_key

    def get_or_create_default(self, org_name: Optional[str] = None) -> str:
        """Return a model API key, mirroring the Model APIs UI behavior.

        For org users, returns an existing key created by the current user when
        available; otherwise creates a default org key. For personal accounts
        without org context, returns the user's global API key.

        Args:
            org_name: Optional organization name. Falls back to config/env resolution.

        Returns:
            str: Raw API key suitable for ``Authorization: Bearer`` headers.
        """
        org = self.resolve_org_context(org_name)
        if org is None:
            return self.get_personal_api_key()

        org_id = org.id
        keys_with_secret = [key for key in self.list(org_id) if key.raw_key]
        if keys_with_secret:
            return keys_with_secret[0].raw_key

        created = self.create(
            org_id,
            _DEFAULT_KEY_NAME,
            description=_DEFAULT_KEY_DESCRIPTION,
        )
        if not created.raw_key:
            raise RuntimeError("API key was created but no secret was returned.")
        return created.raw_key
