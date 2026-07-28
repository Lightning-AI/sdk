"""Show the authenticated caller's identity."""

import json

import rich_click as click
from rich.table import Table

from lightning_sdk.api.auth_api import AuthApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.lightning_cloud.openapi import V1AuthType

_AUTH_TYPE_LABELS = {
    V1AuthType.USER: "user",
    V1AuthType.SCOPED_API_KEY: "scoped-api-key",
}


@click.command("whoami", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output identity as JSON.")
def whoami(as_json: bool = False) -> None:
    """Show who you are authenticated as.

    Works for both a personal login and a scoped API key. For a scoped key it also
    reports the org, project and role the key is bound to.
    """
    identity = AuthApi().whoami()
    auth_type = _AUTH_TYPE_LABELS.get(identity.auth_type, identity.auth_type or "unknown")

    if as_json:
        payload = {
            "auth_type": auth_type,
            "user_id": identity.user_id or None,
            "username": identity.username or None,
            "email": identity.email or None,
            "org_id": identity.org_id or None,
            "project_id": identity.project_id or None,
            "role_id": identity.role_id or None,
            "api_key_id": identity.api_key_id or None,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Auth type", auth_type)
    table.add_row("User ID", identity.user_id or "")
    table.add_row("Username", identity.username or "")
    table.add_row("Email", identity.email or "")
    # org/project/role/api-key are only populated for scoped keys.
    for label, value in (
        ("Org ID", identity.org_id),
        ("Project ID", identity.project_id),
        ("Role ID", identity.role_id),
        ("API key ID", identity.api_key_id),
    ):
        if value:
            table.add_row(label, value)

    click.echo(rich_to_str(table), color=True)
