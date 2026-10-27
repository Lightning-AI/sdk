"""Teamspace list command."""

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.resource_completion import accessible_teamspaces
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str


@click.command("list", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_teamspaces(as_json: bool) -> None:
    """List the Teamspaces you have access to."""
    records = [
        {"owner": owner, "name": name, "id": teamspace_id}
        for owner, teamspaces in sorted(accessible_teamspaces().items())
        for name, teamspace_id in sorted(teamspaces.items())
    ]
    if as_json:
        echo_json({"teamspaces": records})
        return

    table = Table()
    table.add_column("Teamspace")
    for record in records:
        table.add_row(f"{record['owner']}/{record['name']}")
    click.echo(rich_to_str(table), color=True)
