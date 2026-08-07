"""Generic secret commands for the authenticated user."""

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.utils.configuration import read_secret_value, secret_records, validate_name
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.utils.resolve import _get_authed_user


@click.group("secret", cls=LightningGroup)
def secret() -> None:
    """Manage generic secrets for the authenticated user."""


@secret.command("list", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_secrets(as_json: bool) -> None:
    """List generic user secrets."""
    records = secret_records(_get_authed_user().secrets)
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
@click.option("--value-stdin", is_flag=True, default=False, help="Read the secret value from stdin.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def set_secret(key: str, value_stdin: bool, as_json: bool) -> None:
    """Create or update a generic user secret."""
    validate_name(key)
    value = read_secret_value(value_stdin)
    _get_authed_user().set_secret(key, value)
    if as_json:
        echo_json({"name": key, "status": "set"})
        return
    click.echo(f"Secret {key} set.")


@secret.command("delete", cls=LightningCommand)
@click.argument("key")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_secret(key: str, as_json: bool) -> None:
    """Delete a generic user secret."""
    validate_name(key)
    _get_authed_user().delete_secret(key)
    if as_json:
        echo_json({"name": key, "status": "deleted"})
        return
    click.echo(f"Secret {key} deleted.")
