from typing import Dict, List, Optional

from lightning_sdk.api.lit_registry_api import LitRegistryApi
from lightning_sdk.utils.resolve import _resolve_teamspace


class LitRegistry:
    def __init__(self) -> None:
        self._api = LitRegistryApi()

    def list_containers(
        self, teamspace: str, org: Optional[str] = None, user: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """List available containers.

        Args:
            teamspace: The teamspace to list containers from.
            org: The organization to list containers from.
            user: The user to list the containers from.

        Returns:
            A list of dictionaries containing repository details.
        """
        try:
            teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        except Exception as e:
            raise ValueError(f"Could not resolve teamspace: {e}") from e
        project_id = teamspace.id
        repositories = self._api.list_containers(project_id)
        table = []
        for repo in repositories:
            table.append(
                {
                    "REPOSITORY": repo.name,
                    "IMAGE ID": repo.id,
                    "CREATED": repo.creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        return table
