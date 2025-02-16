from typing import Optional

import click

from lightning_sdk.ai_hub import AIHub


@click.group(name="aihub")
def aihub() -> None:
    """Interact with Lightning Studio - AI Hub."""


@aihub.command(name="api-info")
@click.argument("api-id")
def api_info(api_id: str) -> None:
    """Get full API template info such as input details.

    Example:
      lightning aihub api_info API-ID

    API-ID: The ID of the API for which information is requested.
    """
    ai_hub = AIHub()
    ai_hub.api_info(api_id)


@aihub.command(name="list-apis")
@click.option("--search", default=None, help="Search for API templates by name.")
def list_apis(search: Optional[str]) -> None:
    """List API templates available in the AI Hub."""
    ai_hub = AIHub()
    ai_hub.list_apis(search=search)


@aihub.command(name="deploy")
@click.argument("api-id")
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help="Cloud Account to deploy the API to. Defaults to user's default cloud account.",
)
@click.option("--name", default=None, help="Name of the deployed API. Defaults to the name of the API template.")
@click.option(
    "--teamspace",
    default=None,
    help="Teamspace to deploy the API to. Defaults to user's default teamspace.",
)
@click.option(
    "--org",
    default=None,
    help="Organization to deploy the API to. Defaults to user's default organization.",
)
def deploy(
    api_id: str, cloud_account: Optional[str], name: Optional[str], teamspace: Optional[str], org: Optional[str]
) -> None:
    """Deploy an API template from the AI Hub.

    Example:
      lightning aihub deploy API-ID

    API-ID: The ID of the API which should be deployed.
    """
    ai_hub = AIHub()
    ai_hub.run(api_id, cloud_account=cloud_account, name=name, teamspace=teamspace, org=org)
