from lightning_sdk.lightning_cloud.openapi import V1Project
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class TeamspaceApi:
    """Internal API client for Teamspace requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    def get_teamspace(self, name: str, owner_id: str, is_user: bool) -> V1Project:
        """Get the current teamspace from the owner."""
        kwargs = {}

        if is_user:
            # this will use the currently authenticated user
            kwargs["filter_by_user_id"] = True
        else:
            kwargs["organization_id"] = owner_id
        res = self._client.projects_service_list_memberships(**kwargs)
        _membership = [el for el in res.memberships if el.display_name == name or el.name == name]
        if not _membership:
            raise ValueError(f"Teamspace {name} does not exist")
        project_id = _membership[0].project_id
        self._client.projects_service_list_memberships()
        return self._client.projects_service_get_project(project_id)

    def _get_teamspace_by_id(self, teamspace_id: str) -> V1Project:
        return self._client.projects_service_get_project(teamspace_id)
