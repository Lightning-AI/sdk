"""List the roles in a teamspace."""

import json
from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.auth_api import AuthApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.utils.resolve import _get_authed_user

_TEAMSPACE_HELP = "Teamspace to list roles for, as 'owner/teamspace'. Falls back to your default teamspace."


@click.command("roles", cls=LightningCommand)
@click.option("--teamspace", help=_TEAMSPACE_HELP)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output roles as JSON.")
def roles(teamspace: Optional[str] = None, as_json: bool = False) -> None:
    """List the roles in a teamspace and mark which ones you hold."""
    resolved = TeamspacesMenu()(teamspace=teamspace)
    api = AuthApi()
    mine = api.my_role_ids(resolved.id, _get_authed_user().id)

    rows = [
        {
            "id": role.id,
            "name": role.name,
            "description": role.description or "",
            "permissions": len(role.rules or []),
            "yours": role.id in mine,
        }
        for role in api.list_roles(resolved.id)
    ]

    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return

    table = Table(title=f"Roles for {resolved.owner.name}/{resolved.name}")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Permissions", justify="right")
    table.add_column("Yours")
    for row in rows:
        table.add_row(row["name"], row["description"], str(row["permissions"]), "✓" if row["yours"] else "")

    click.echo(rich_to_str(table), color=True)
