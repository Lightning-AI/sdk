from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    OrganizationsServiceApi,
    V1Organization,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class OrgApi:
    """Internal API client for org requests (mainly http requests)."""

    def __init__(self) -> None:
        super().__init__()

        # TODO: add org API to client in lightning_cloud
        self._client = OrganizationsServiceApi(api_client=LightningClient(max_tries=3).api_client)

    def get_org(self, name: str) -> V1Organization:
        """Gets the organization from the given name."""
        auth = Auth()
        auth.authenticate()
        user_id = auth.user_id
        res = self._client.organizations_service_list_organizations(user_id=user_id)
        org = [el for el in res.organizations if el.display_name == name or el.name == name]
        if not org:
            raise ValueError(f"Org {name} does not exist")
        return org[0]

    def _get_org_by_id(self, org_id: str) -> V1Organization:
        """Gets the organization from the given ID."""
        return self._client.organizations_service_get_organization(org_id)
