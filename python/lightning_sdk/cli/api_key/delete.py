"""Delete an org-scoped API key."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP, resolve_org
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("delete", cls=LightningCommand)
@click.argument("key_id")
@click.option("--org", help=ORG_OPTION_HELP)
def delete_api_key(key_id: str, org: Optional[str]) -> None:
    """Delete an org-scoped API key."""
    organization = resolve_org(org)
    api = ApiKeyApi()
    api.delete(organization.id, key_id)
    click.echo(f"Deleted API key {key_id}.")
