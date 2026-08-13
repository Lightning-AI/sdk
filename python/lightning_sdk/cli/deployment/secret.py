"""Deployment secret-reference commands."""

from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.utils.configuration import deployment_secret_records, validate_name
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand, LightningGroup
from lightning_sdk.cli.utils.resource_resolution import resolve_deployment
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace, teamspace_option


@click.group("secret", cls=LightningGroup)
def secret() -> None:
    """Manage Deployment secret references."""


@secret.command("list", cls=LightningCommand)
@click.option("--name", required=True, help="Deployment name.")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_secret(
    name: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """List teamspace secrets referenced by the Deployment."""
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    deployment = resolve_deployment(name, resolved_teamspace)
    records = deployment_secret_records(deployment.env or [])
    if as_json:
        echo_json({"secrets": records})
        return

    table = Table()
    table.add_column("Environment name")
    table.add_column("From secret")
    for record in records:
        table.add_row(record["name"], record["from_secret"])
    click.echo(rich_to_str(table), color=True)


@secret.command("set", cls=LightningCommand)
@click.argument("assignment")
@click.option("--name", required=True, help="Deployment name.")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def set_secret(
    assignment: str,
    name: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Reference a teamspace secret. Use SECRET, or ENV_NAME=SECRET to inject under a different env var name."""
    left, sep, right = assignment.partition("=")
    env_name: Optional[str]
    if sep and right:
        env_name, secret_name = left, right
        validate_name(env_name)
    else:
        env_name, secret_name = None, left
    validate_name(secret_name)
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    deployment = resolve_deployment(name, resolved_teamspace)
    deployment.set_secret(secret_name, env_name)
    injected = env_name or secret_name
    if as_json:
        echo_json({"name": injected, "from_secret": secret_name, "status": "set"})
        return
    click.echo(f"Secret {secret_name} set as {injected}.")


@secret.command("delete", cls=LightningCommand)
@click.argument("env_name")
@click.option("--name", required=True, help="Deployment name.")
@teamspace_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_secret(
    env_name: str,
    name: str,
    teamspace: Optional[str],
    org: Optional[str],
    user: Optional[str],
    as_json: bool,
) -> None:
    """Remove a teamspace secret reference by its injected environment variable name."""
    validate_name(env_name)
    resolved_teamspace = resolve_teamspace(teamspace=teamspace, org=org, user=user)
    deployment = resolve_deployment(name, resolved_teamspace)
    deployment.delete_secret(env_name)
    if as_json:
        echo_json({"name": env_name, "status": "deleted"})
        return
    click.echo(f"Secret {env_name} deleted.")
