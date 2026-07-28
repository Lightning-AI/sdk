"""Create an org-scoped API key."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP, resolve_org
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("create", cls=LightningCommand)
@click.option("--org", help=ORG_OPTION_HELP)
@click.option("--name", default="Default", show_default=True, help="Display name for the key.")
@click.option(
    "--description",
    default="",
    help='Optional description. Defaults to "Auto-created for model API access" when --name is Default.',
)
@click.option("--role", "role_id", help="Role ID to assign. Defaults to the org member role.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output the created key as JSON.")
def create_api_key(
    org: Optional[str],
    name: str,
    description: str,
    role_id: Optional[str],
    as_json: bool = False,
) -> None:
    """Create an org-scoped API key for model API access."""
    organization = resolve_org(org)
    api = ApiKeyApi()
    created = api.create(organization.id, name, role_id=role_id, description=description)
    if not created.raw_key:
        raise click.ClickException("API key was created but no secret was returned.")
    if as_json:
        echo_json({"id": created.id, "name": created.name, "raw_key": created.raw_key})
        return
    click.echo(created.raw_key)
