from lightning_sdk.lightning_cloud.openapi import (
    V1Organization,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class OrgApi:
    """Internal API client for org requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_org(self, name: str) -> V1Organization:
        """Gets the organization from the given name."""
        res = self._client.organizations_service_get_organization(id="", name=name)
        if not res:
            raise ValueError(f"Org {name} does not exist")
        return res

    def _get_org_by_id(self, org_id: str) -> V1Organization:
        """Gets the organization from the given ID."""
        return self._client.organizations_service_get_organization(id=org_id)
