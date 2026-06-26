"""SSH CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register SSH commands with the given group."""
    from lightning_sdk.cli.ssh.configure import configure_ssh
    from lightning_sdk.cli.ssh.generate import generate_ssh

    group.add_command(configure_ssh, name="configure")
    group.add_command(generate_ssh, name="generate")
