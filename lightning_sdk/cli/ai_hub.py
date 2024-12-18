from typing import List, Optional

from lightning_sdk.ai_hub import AIHub
from lightning_sdk.cli.studios_menu import _StudiosMenu


class _AIHub(_StudiosMenu):
    """Interact with Lightning Studio - AI Hub."""

    def __init__(self) -> None:
        self._hub = AIHub()

    def api_info(self, api_id: str) -> dict:
        """Get full API template info such as input details.

        Example:
          lightning aihub api_info [API_ID]

        Args:
          api_id: The ID of the API for which information is requested.
        """
        return self._hub.api_info(api_id)

    def list_apis(self, search: Optional[str] = None) -> List[dict]:
        """List API templates available in the AI Hub.

        Args:
          search: Search for API templates by name.
        """
        return self._hub.list_apis(search=search)

    def deploy(
        self,
        api_id: str,
        cloud_account: Optional[str] = None,
        name: Optional[str] = None,
        teamspace: Optional[str] = None,
        org: Optional[str] = None,
    ) -> dict:
        """Deploy an API template from the AI Hub.

        Args:
          api_id: API template ID.
          cloud_account: Cloud Account to deploy the API to. Defaults to user's default cloud account.
          name: Name of the deployed API. Defaults to the name of the API template.
          teamspace: Teamspace to deploy the API to. Defaults to user's default teamspace.
          org: Organization to deploy the API to. Defaults to user's default organization.
        """
        return self._hub.run(api_id, cloud_account=cloud_account, name=name, teamspace=teamspace, org=org)
