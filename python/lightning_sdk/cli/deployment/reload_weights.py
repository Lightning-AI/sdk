"""Deployment reload-weights command."""

from typing import Optional

import click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import resolve_deployment, resolve_teamspace


@click.command("reload-weights")
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
def reload_weights(name: str, teamspace: Optional[str] = None) -> None:
    """Reload weights on a running BYOM deployment."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)
    response = api.reload_weights(deployment)
    click.echo(f"Weights reloaded (version {response.weight_version}).")
