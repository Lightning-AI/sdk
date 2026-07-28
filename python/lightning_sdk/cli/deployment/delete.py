"""Deployment delete command."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import resolve_deployment
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace


@click.command("delete", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--yes", "-y", is_flag=True, default=False, help="Do not prompt for confirmation.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def delete_deployment(name: str, teamspace: Optional[str] = None, yes: bool = False, as_json: bool = False) -> None:
    """Delete a deployment."""
    if not yes:
        raise click.UsageError("Deleting a deployment requires --yes.")

    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)

    api.delete_deployment(deployment)
    if as_json:
        echo_json({"name": deployment.name, "deleted": True})
        return
    click.echo(f"Deleted deployment {deployment.name}.")
