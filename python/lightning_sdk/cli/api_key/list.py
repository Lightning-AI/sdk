"""List org-scoped API keys."""

from typing import Optional

import click
from rich.table import Table

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP, resolve_org
from lightning_sdk.cli.utils.richt_print import rich_to_str


@click.command("list")
@click.option("--org", help=ORG_OPTION_HELP)
@click.option(
    "--all-users",
    is_flag=True,
    default=False,
    help="Include API keys created by other org members.",
)
def list_api_keys(org: Optional[str], all_users: bool) -> None:
    """List org-scoped API keys.

    The secret is only shown when the backend can decrypt it (typically keys you created).
    """
    organization = resolve_org(org)
    api = ApiKeyApi()
    keys = api.list(organization.id, mine_only=not all_users)

    table = Table(title=f"API keys for {organization.name}")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Created")
    table.add_column("Secret visible")

    for key in keys:
        table.add_row(
            key.id or "",
            key.name or "",
            key.description or "",
            key.created_at.isoformat() if key.created_at else "",
            "yes" if key.raw_key else "no",
        )

    click.echo(rich_to_str(table), color=True)
