"""Machine CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register machine commands with the given group."""
    from lightning_sdk.cli.machine.list import list_machines

    group.add_command(list_machines, name="list")
