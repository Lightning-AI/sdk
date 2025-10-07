"""Base Studio CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register base studio commands with the given group."""
    from lightning_sdk.cli.base_studio.list import list_base_studios

    group.add_command(list_base_studios)
