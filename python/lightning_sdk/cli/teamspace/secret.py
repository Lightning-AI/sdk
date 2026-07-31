"""Generic Teamspace secret commands."""

from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.utils.configuration import read_secret_value, secret_records, validate_name
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace, teamspace_option


@click.group("secret", cls=LightningGroup)
def secret() -> None:
    """Manage generic Teamspace secrets."""


@secret.command("list", cls=LightningCommand)
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_secrets(teamspace: Optional[str], org: Optional[str], user: Optional[str], as_json: bool) -> None:
    """List generic Teamspace secrets."""
    resolved = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    records = secret_records(resolved.secrets)
    if as_json:
        echo_json({"secrets": records})
        return

    table = Table()
    table.add_column("Name")
    table.add_column("Value")
    for record in records:
        table.add_row(record["name"], record["value"])
    click.echo(rich_to_str(table), color=True)


@secret.command("set", cls=LightningCommand)
@click.argument("key")
@teamspace_option
@click.option("--value-stdin", is_flag=True, default=False, help="Read the secret value from stdin.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def set_secret(
    key: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    value_stdin: bool,
    as_json: bool,
) -> None:
    """Create or update a generic Teamspace secret."""
    validate_name(key)
    value = read_secret_value(value_stdin)
    resolved = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    resolved.set_secret(key, value)
    if as_json:
        echo_json({"name": key, "status": "set"})
        return
    click.echo(f"Secret {key} set.")


@secret.command("delete", cls=LightningCommand)
@click.argument("key")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_secret(
    key: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Delete a generic Teamspace secret."""
    validate_name(key)
    resolved = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    resolved.delete_secret(key)
    if as_json:
        echo_json({"name": key, "status": "deleted"})
        return
    click.echo(f"Secret {key} deleted.")
