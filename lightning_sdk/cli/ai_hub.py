from typing import List, Optional

from lightning_sdk.ai_hub import AIHub
from lightning_sdk.cli.studios_menu import _StudiosMenu


class _AIHub(_StudiosMenu):
    """Interact with Lightning Studio - AI Hub."""

    def __init__(self) -> None:
        self._hub = AIHub()

    def list_apis(self, search: Optional[str] = None) -> List[dict]:
        """List API templates available in the AI Hub.

        Args:
          search: Search for API templates by name.
        """
        return self._hub.list_apis(search=search)

    def deploy(
        self,
        api_id: str,
        cluster: Optional[str] = None,
        name: Optional[str] = None,
        teamspace: Optional[str] = None,
        org: Optional[str] = None,
    ) -> dict:
        """Deploy an API template from the AI Hub.

        Args:
          api_id: API template ID.
          cluster: Cluster to deploy the API to. Defaults to user's default cluster.
          name: Name of the deployed API. Defaults to the name of the API template.
          teamspace: Teamspace to deploy the API to. Defaults to user's default teamspace.
          org: Organization to deploy the API to. Defaults to user's default organization.
        """
        return self._hub.deploy(api_id, cluster=cluster, name=name, teamspace=teamspace, org=org)
