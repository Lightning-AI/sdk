"""Deployment environment-variable commands."""

from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.utils.configuration import (
    deployment_environment_records,
    parse_assignment,
    validate_name,
)
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup
from lightning_sdk.cli.utils.resource_resolution import resolve_deployment
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace, teamspace_option


@click.group("env", cls=LightningGroup)
def env() -> None:
    """Manage Deployment environment variables."""


@env.command("list", cls=LightningCommand)
@click.option("--name", required=True, help="Deployment name.")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_env(
    name: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """List directly configured Deployment environment variables."""
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    deployment = resolve_deployment(name, resolved_teamspace)
    records = deployment_environment_records(deployment.env or [])
    if as_json:
        echo_json({"environment_variables": records})
        return

    table = Table()
    table.add_column("Name")
    table.add_column("Value")
    table.add_column("From secret")
    for record in records:
        table.add_row(record["name"], record.get("value", ""), record.get("from_secret", ""))
    click.echo(rich_to_str(table), color=True)


@env.command("set", cls=LightningCommand)
@click.argument("assignment")
@click.option("--name", required=True, help="Deployment name.")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def set_env(
    assignment: str,
    name: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Set one Deployment environment variable from KEY=VALUE."""
    key, value = parse_assignment(assignment)
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    deployment = resolve_deployment(name, resolved_teamspace)
    deployment.set_env({key: value})
    if as_json:
        echo_json({"name": key, "status": "set"})
        return
    click.echo(f"Environment variable {key} set.")


@env.command("delete", cls=LightningCommand)
@click.argument("key")
@click.option("--name", required=True, help="Deployment name.")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_env(
    key: str,
    name: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Delete one directly configured Deployment environment variable."""
    validate_name(key)
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    deployment = resolve_deployment(name, resolved_teamspace)
    deployment.delete_env(key)
    if as_json:
        echo_json({"name": key, "status": "deleted"})
        return
    click.echo(f"Environment variable {key} deleted.")
