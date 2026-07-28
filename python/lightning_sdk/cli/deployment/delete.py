"""Deployment delete command."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import resolve_deployment
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace


@click.command("delete", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--yes", "-y", is_flag=True, default=False, help="Do not prompt for confirmation.")
def delete_deployment(name: str, teamspace: Optional[str] = None, yes: bool = False) -> None:
    """Delete a deployment."""
    if not yes:
        raise click.UsageError("Deleting a deployment requires --yes.")

    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)

    api.delete_deployment(deployment)
    click.echo(f"Deleted deployment {deployment.name}.")
