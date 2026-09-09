"""VM CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register VM commands with the given group."""
    from lightning_sdk.cli.vm.create import create_vm
    from lightning_sdk.cli.vm.list import list_vms

    group.add_command(create_vm, name="create")
    group.add_command(list_vms, name="list")
