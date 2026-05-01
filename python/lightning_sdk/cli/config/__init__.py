"""Config CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register config commands with the given group."""
    from lightning_sdk.cli.config.get import get
    from lightning_sdk.cli.config.set import set_value
    from lightning_sdk.cli.config.show import show

    group.add_command(get)
    group.add_command(set_value)
    group.add_command(show)
