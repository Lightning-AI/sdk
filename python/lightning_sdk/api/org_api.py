from lightning_sdk.lightning_cloud.openapi import (
    V1CreateProjectRequest,
    V1Organization,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class OrgApi:
    """Internal API client for org requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_org(self, name: str) -> V1Organization:
        """Fetch an organisation by name.

        Args:
            name: The organisation name to look up.

        Returns:
            V1Organization: The matching organisation record.

        Raises:
            ValueError: If no organisation with the given name exists.
        """
        res = self._client.organizations_service_get_organization(id="", name=name)
        if not res:
            raise ValueError(f"Org {name} does not exist")
        return res

    def _get_org_by_id(self, org_id: str) -> V1Organization:
        """Gets the organization from the given ID.

        Args:
            org_id: The unique ID of the organisation to retrieve.

        Returns:
            V1Organization: The matching organisation record.
        """
        return self._client.organizations_service_get_organization(id=org_id)

    def create_teamspace(self, name: str, organization_id: str) -> None:
        """Create a new teamspace owned by the given organisation.

        Args:
            name: The display name for the new teamspace.
            organization_id: The ID of the owning organisation.
        """
        self._client.projects_service_create_project(
            body=V1CreateProjectRequest(name=name, organization_id=organization_id, display_name=name)
        )
