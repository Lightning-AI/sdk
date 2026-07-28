"""Deployment inspect command."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import deployment_to_dict, resolve_deployment
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace


@click.command("inspect", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--jobs", "include_jobs", is_flag=True, default=False, help="Include jobs for this deployment.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON (inspect always emits JSON).")
def inspect_deployment(
    name: str,
    teamspace: Optional[str] = None,
    include_jobs: bool = False,
    as_json: bool = False,
) -> None:
    """Inspect a deployment as JSON."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = DeploymentApi()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)
    data = deployment_to_dict(deployment)

    if include_jobs:
        jobs = api.list_deployment_jobs(resolved_teamspace.id, deployment.id, limit=100)
        data["jobs"] = [job.to_dict() for job in jobs]

    echo_json(data)
