"""Deployment inspect command."""

from typing import Optional

import click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import deployment_to_dict, resolve_deployment, resolve_teamspace, to_json


@click.command("inspect")
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--jobs", "include_jobs", is_flag=True, default=False, help="Include jobs for this deployment.")
def inspect_deployment(name: str, teamspace: Optional[str] = None, include_jobs: bool = False) -> None:
    """Inspect a deployment as JSON."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)
    data = deployment_to_dict(deployment)

    if include_jobs:
        jobs = api.list_deployment_jobs(resolved_teamspace.id, deployment.id, limit=100)
        data["jobs"] = [job.to_dict() for job in jobs]

    click.echo(to_json(data))
