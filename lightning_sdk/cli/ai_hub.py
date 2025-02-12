from typing import Optional

import click

from lightning_sdk.ai_hub import AIHub
from lightning_sdk.cli.studios_menu import _StudiosMenu


class _AIHub(_StudiosMenu):
    """Interact with Lightning Studio - AI Hub."""

    def api_info(self, api_id: str) -> None:
        """Get full API template info such as input details.

        Example:
          lightning aihub api_info [API_ID]

        Args:
          api_id: The ID of the API for which information is requested.
        """
        return api_info(api_id=api_id)

    def list_apis(self, search: Optional[str] = None) -> None:
        """List API templates available in the AI Hub.

        Args:
          search: Search for API templates by name.
        """
        return list_apis(search=search)

    def deploy(
        self,
        api_id: str,
        cloud_account: Optional[str] = None,
        name: Optional[str] = None,
        teamspace: Optional[str] = None,
        org: Optional[str] = None,
    ) -> None:
        """Deploy an API template from the AI Hub.

        Args:
          api_id: API template ID.
          cloud_account: Cloud Account to deploy the API to. Defaults to user's default cloud account.
          name: Name of the deployed API. Defaults to the name of the API template.
          teamspace: Teamspace to deploy the API to. Defaults to user's default teamspace.
          org: Organization to deploy the API to. Defaults to user's default organization.
        """
        return deploy(api_id=api_id, cloud_account=cloud_account, name=name, teamspace=teamspace, org=org)


@click.group(name="aihub")
def aihub() -> None:
    """Interact with Lightning Studio - AI Hub."""


# @aihub.command(name="api-info")
# @click.argument("api-id")
def api_info(api_id: str) -> None:
    """Get full API template info such as input details.

    Example:
      lightning aihub api_info API-ID

    API-ID: The ID of the API for which information is requested.
    """
    ai_hub = AIHub()
    ai_hub.api_info(api_id)


# @aihub.command(name="list-apis")
# @click.option("--search", default=None, help="Search for API templates by name.")
def list_apis(search: Optional[str]) -> None:
    """List API templates available in the AI Hub."""
    ai_hub = AIHub()
    ai_hub.list_apis(search=search)


# @aihub.command(name="deploy")
# @click.argument("api-id")
# @click.option(
#     "--cloud-account",
#     default=None,
#     help="Cloud Account to deploy the API to. Defaults to user's default cloud account.",
# )
# @click.option("--name", default=None, help="Name of the deployed API. Defaults to the name of the API template.")
# @click.option(
#     "--teamspace",
#     default=None,
#     help="Teamspace to deploy the API to. Defaults to user's default teamspace.",
# )
# @click.option(
#     "--org",
#     default=None,
#     help="Organization to deploy the API to. Defaults to user's default organization.",
# )
def deploy(
    api_id: str, cloud_account: Optional[str], name: Optional[str], teamspace: Optional[str], org: Optional[str]
) -> None:
    ai_hub = AIHub()
    ai_hub.run(api_id, cloud_account=cloud_account, name=name, teamspace=teamspace, org=org)
