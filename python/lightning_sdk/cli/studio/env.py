"""Studio environment-variable commands."""

from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.resource_completion import complete_studio
from lightning_sdk.cli.utils.configuration import environment_records, parse_assignment, validate_name
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup
from lightning_sdk.cli.utils.resource_resolution import resolve_studio
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace, teamspace_option


@click.group("env", cls=LightningGroup)
def env() -> None:
    """Manage Studio environment variables."""


@env.command("list", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
    shell_complete=complete_studio,
)
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_env(
    name: Optional[str],
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """List directly configured Studio environment variables."""
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    studio = resolve_studio(name, resolved_teamspace)
    records = environment_records(studio.env)
    if as_json:
        echo_json({"environment_variables": records})
        return

    table = Table()
    table.add_column("Name")
    table.add_column("Value")
    for record in records:
        table.add_row(record["name"], record["value"])
    click.echo(rich_to_str(table), color=True)


@env.command("set", cls=LightningCommand)
@click.argument("assignment")
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
    shell_complete=complete_studio,
)
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def set_env(
    assignment: str,
    name: Optional[str],
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Set one Studio environment variable from KEY=VALUE."""
    key, value = parse_assignment(assignment)
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    studio = resolve_studio(name, resolved_teamspace)
    studio.set_env({key: value})
    if as_json:
        echo_json({"name": key, "status": "set"})
        return
    click.echo(f"Environment variable {key} set.")


@env.command("delete", cls=LightningCommand)
@click.argument("key")
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
    shell_complete=complete_studio,
)
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_env(
    key: str,
    name: Optional[str],
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Delete one directly configured Studio environment variable."""
    validate_name(key)
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    studio = resolve_studio(name, resolved_teamspace)
    studio.delete_env(key)
    if as_json:
        echo_json({"name": key, "status": "deleted"})
        return
    click.echo(f"Environment variable {key} deleted.")
