"""Deployment list command."""

from typing import Callable, Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.deployment_api import DeploymentApi
from lightning_sdk.cli.deployment.common import iter_teamspaces
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.lightning_cloud.openapi import V1Deployment


@click.command("list", cls=LightningCommand)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option(
    "--all",
    "all_teamspaces",
    is_flag=True,
    flag_value=True,
    default=False,
    help="List deployments in all teamspaces visible to the selected owner.",
)
@click.option(
    "--sort-by",
    default=None,
    type=click.Choice(
        [
            "name",
            "teamspace",
            "state",
            "replicas",
            "ready",
            "pending",
            "failing",
            "machine",
            "source",
            "cloud-account",
        ],
        case_sensitive=False,
    ),
    help="The attribute to sort deployments by.",
)
def list_deployments(
    teamspace: Optional[str] = None,
    all_teamspaces: bool = False,
    sort_by: Optional[str] = None,
) -> None:
    """List deployments in a teamspace."""
    api = DeploymentApi()
    rows = []
    for resolved_teamspace in iter_teamspaces(teamspace, all_teamspaces):
        deployments = api.list_deployments(resolved_teamspace.id, limit=100)
        rows.extend((resolved_teamspace, deployment) for deployment in deployments)

    table = Table(pad_edge=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Teamspace", no_wrap=True)
    table.add_column("State", no_wrap=True)
    table.add_column("Replicas", no_wrap=True)
    table.add_column("Machine", no_wrap=True)
    table.add_column("Source", overflow="fold")
    table.add_column("Cloud account", no_wrap=True)

    for resolved_teamspace, deployment in sorted(rows, key=_sort_key(sort_by)):
        spec = deployment.spec
        table.add_row(
            deployment.name or "",
            f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}",
            _state(deployment),
            _replicas(deployment),
            _string(getattr(spec, "instance_name", None) or getattr(spec, "instance_type", None)),
            _source_label(deployment),
            _string(getattr(spec, "cluster_id", None)),
        )

    click.echo(rich_to_str(table), color=True)


def _sort_key(sort_by: Optional[str]) -> Callable:
    sort_key_map = {
        "name": lambda item: str(item[1].name or ""),
        "teamspace": lambda item: str(item[0].name or ""),
        "state": lambda item: _state(item[1]),
        "replicas": lambda item: int(item[1].replicas or 0),
        "ready": lambda item: int(getattr(item[1].status, "ready_replicas", 0) or 0),
        "pending": lambda item: int(getattr(item[1].status, "pending_replicas", 0) or 0),
        "failing": lambda item: int(getattr(item[1].status, "failing_replicas", 0) or 0),
        "machine": lambda item: str(getattr(item[1].spec, "instance_name", None) or ""),
        "source": lambda item: _source_label(item[1]),
        "cloud-account": lambda item: str(getattr(item[1].spec, "cluster_id", None) or ""),
    }
    return sort_key_map.get(sort_by, lambda item: str(item[1].name or ""))


def _source_label(deployment: V1Deployment) -> str:
    byom = getattr(deployment, "byom_spec", None)
    if byom and getattr(byom, "served_model_name", None):
        return f"model:{byom.served_model_name}"
    spec = deployment.spec
    if getattr(spec, "image", None):
        return f"image:{spec.image}"
    cloudspace_id = getattr(deployment, "cloudspace_id", None) or getattr(spec, "cloudspace_id", None)
    if cloudspace_id:
        return f"studio:{cloudspace_id}"
    return ""


def _state(deployment: V1Deployment) -> str:
    status = deployment.status
    state = _string(
        getattr(status, "first_job_state_current_release", None)
        or getattr(status, "message", None)
        or deployment.current_state
        or deployment.desired_state
    )
    return state.removeprefix("DEPLOYMENT_STATE_")


def _replicas(deployment: V1Deployment) -> str:
    status = deployment.status
    desired = deployment.replicas
    ready = getattr(status, "ready_replicas", None)
    pending = getattr(status, "pending_replicas", None)
    failing = getattr(status, "failing_replicas", None)

    if ready is None:
        return _string(desired)

    summary = f"{ready}/{desired}" if desired is not None else str(ready)
    details = []
    if pending:
        details.append(f"{pending} pending")
    if failing:
        details.append(f"{failing} failing")
    if details:
        return f"{summary} ({', '.join(details)})"
    return summary


def _string(value: object) -> str:
    if value is None:
        return ""
    return str(value)
