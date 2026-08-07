"""API client for identity and authorization introspection."""

from typing import List, Set

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import V1Role, V1WhoamiResponse


class AuthApi:
    """API client for identity and authorization introspection."""

    def __init__(self) -> None:
        self._client = cached_lightning_client()

    def whoami(self) -> V1WhoamiResponse:
        """Return the authenticated caller's identity.

        Works for both a personal user key and a scoped API key; a scoped key also
        reports the org, project and role it is bound to.
        """
        return self._client.auth_service_whoami()

    def list_roles(self, teamspace_id: str) -> List[V1Role]:
        """List the roles defined in a teamspace."""
        response = self._client.projects_service_list_project_roles(project_id=teamspace_id)
        return response.roles or []

    def get_role(self, teamspace_id: str, role_id: str) -> V1Role:
        """Fetch a single teamspace role, including its permission rules."""
        return self._client.projects_service_get_project_role(project_id=teamspace_id, id=role_id)

    def my_role_ids(self, teamspace_id: str, user_id: str) -> Set[str]:
        """Return the ids of roles the given user holds in the teamspace."""
        response = self._client.projects_service_list_project_membership_role_bindings(
            project_id=teamspace_id, user_id=user_id
        )
        bindings = response.membership_role_bindings or []
        return {b.role_id for b in bindings if not b.inactive}
