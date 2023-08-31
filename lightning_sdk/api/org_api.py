from lightning_cloud.openapi import V1Organization, OrganizationsServiceApi
from lightning.app.utilities.network import LightningClient

from lightning_cloud.login import Auth


class OrgApi:
    def __init__(self):
        super().__init__()

        # TODO: add org API to client in lightning_cloud
        self._client = OrganizationsServiceApi(api_client=LightningClient().api_client)
    
    def get_org(self, name: str) -> V1Organization:
        auth = Auth()
        auth.authenticate()
        user_id = auth.user_id
        res = self._client.organizations_service_list_organizations(user_id=user_id)
        org = [el for el in res.organizations if el.display_name == name or el.name == name]
        if not org:
            raise ValueError(f"Org {name} does not exist")
        return org[0]
