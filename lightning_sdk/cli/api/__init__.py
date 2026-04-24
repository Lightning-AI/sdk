"""API CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register API commands with the given group."""
    from lightning_sdk.cli.api.deploy import deploy_api
    from lightning_sdk.cli.api.dockerize import dockerize_api

    group.add_command(deploy_api, name="deploy")
    group.add_command(dockerize_api, name="dockerize")
