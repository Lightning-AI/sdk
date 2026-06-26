"""Deployment CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register deployment commands with the given group."""
    from lightning_sdk.cli.deployment.create import create_deployment
    from lightning_sdk.cli.deployment.delete import delete_deployment
    from lightning_sdk.cli.deployment.inspect import inspect_deployment
    from lightning_sdk.cli.deployment.list import list_deployments
    from lightning_sdk.cli.deployment.logs import deployment_logs
    from lightning_sdk.cli.deployment.reload_weights import reload_weights
    from lightning_sdk.cli.deployment.update import update_deployment

    group.add_command(create_deployment, name="create")
    group.add_command(list_deployments, name="list")
    group.add_command(inspect_deployment, name="inspect")
    group.add_command(update_deployment, name="update")
    group.add_command(delete_deployment, name="delete")
    group.add_command(deployment_logs, name="logs")
    group.add_command(reload_weights, name="reload-weights")
