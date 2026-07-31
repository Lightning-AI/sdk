"""Authenticated-user CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register authenticated-user commands."""
    from lightning_sdk.cli.user.secret import secret

    group.add_command(secret)
