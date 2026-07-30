"""Deployment deletion resolver."""

from functools import partial
from typing import Optional

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import resolve_deployment
from lightning_sdk.cli.utils.delete import DeleteAction
from lightning_sdk.cli.utils.teamspace_option import resolve_teamspace


def resolve_deployment_delete(
    resource_cls: type[DeploymentApi],
    name: str,
    teamspace: Optional[str],
) -> DeleteAction:
    """Resolve a deployment and return its bound deletion action."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = resource_cls()
    deployment = resolve_deployment(api, resolved_teamspace.id, name)
    return partial(api.delete_deployment, deployment)
