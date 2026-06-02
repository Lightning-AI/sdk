"""Create an org-scoped API key."""

from typing import Optional

import click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP, resolve_org


@click.command("create")
@click.option("--org", help=ORG_OPTION_HELP)
@click.option("--name", default="Default", show_default=True, help="Display name for the key.")
@click.option(
    "--description",
    default="",
    help='Optional description. Defaults to "Auto-created for model API access" when --name is Default.',
)
@click.option("--role", "role_id", help="Role ID to assign. Defaults to the org member role.")
def create_api_key(
    org: Optional[str],
    name: str,
    description: str,
    role_id: Optional[str],
) -> None:
    """Create an org-scoped API key for model API access."""
    organization = resolve_org(org)
    api = ApiKeyApi()
    created = api.create(organization.id, name, role_id=role_id, description=description)
    if not created.raw_key:
        raise click.ClickException("API key was created but no secret was returned.")
    click.echo(created.raw_key)
