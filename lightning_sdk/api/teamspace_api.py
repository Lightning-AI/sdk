from lightning.app.utilities.network import LightningClient
from lightning_cloud.openapi import V1Project


class TeamspaceApi:
    def __init__(self) -> None:
        super().__init__()

        self._client = LightningClient()

    def get_teamspace(
        self,
        name: str,
        org_id: str,
    ) -> V1Project:
        # _org = get_org(client, org)
        res = self._client.projects_service_list_memberships(organization_id=org_id)
        _membership = [el for el in res.memberships if el.display_name == name or el.name == name]
        if not _membership:
            raise ValueError(f"Teamspace {name} does not exist")
        project_id = _membership[0].project_id
        return self._client.projects_service_get_project(project_id)
