"""Teamspace CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register Teamspace commands."""
    from lightning_sdk.cli.teamspace.secret import secret

    group.add_command(secret)
