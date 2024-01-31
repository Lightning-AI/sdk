from typing import List, Optional

from lightning_sdk.lightning_cloud.openapi import V1CloudSpace, V1Project, V1ProjectClusterBinding
from lightning_sdk.lightning_cloud.rest_client import LightningClient

__all__ = ["TeamspaceApi"]


class TeamspaceApi:
    """Internal API client for Teamspace requests (mainly http requests)."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=3)

    def get_teamspace(self, name: str, owner_id: str) -> V1Project:
        """Get the current teamspace from the owner."""
        teamspaces = self.list_teamspaces(name=name, owner_id=owner_id)

        if len(teamspaces) == 0:
            raise ValueError(f"Teamspace {name} does not exist")

        if len(teamspaces) > 1:
            raise RuntimeError(f"{name} is no unique name for a Teamspace")

        return teamspaces[0]

    def _get_teamspace_by_id(self, teamspace_id: str) -> V1Project:
        return self._client.projects_service_get_project(teamspace_id)

    def list_teamspaces(self, owner_id: str, name: Optional[str]) -> Optional[V1Project]:
        """Lists teamspaces from owner.

        If name is passed only teamspaces matching that name will be returned

        """
        # cannot list projects the authed user is not a member of
        # -> list projects authed users are members of + filter later on
        res = self._client.projects_service_list_memberships(filter_by_user_id=True)

        return [
            self._get_teamspace_by_id(m.project_id)
            for m in filter(
                # only return teamspaces actually owned by the id
                lambda x: x.owner_id == owner_id,
                # if name is provided, filter for teamspaces matching that name
                filter(lambda x: name is None or x.name == name or x.display_name == name, res.memberships),
            )
        ]

    def list_studios(self, teamspace_id: str, cluster_id: Optional[str] = None) -> List[V1CloudSpace]:
        """List studios in teamspace."""
        kwargs = {"project_id": teamspace_id}

        if cluster_id is not None:
            kwargs["cluster_id"] = cluster_id

        cloudspaces = []

        while True:
            resp = self._client.cloud_space_service_list_cloud_spaces(**kwargs)
            cloudspaces.extend(resp.cloudspaces)
            if not resp.next_page_token:
                break

            kwargs["page_token"] = resp.next_page_token

        return cloudspaces

    def list_clusters(self, teamspace_id: str) -> List[V1ProjectClusterBinding]:
        """Lists clusters in a teamspace."""
        return self._client.projects_service_list_project_cluster_bindings(project_id=teamspace_id).clusters
