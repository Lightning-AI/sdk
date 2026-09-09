"""VM CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register VM commands with the given group."""
    from lightning_sdk.cli.vm.create import create_vm
    from lightning_sdk.cli.vm.delete import delete_vm
    from lightning_sdk.cli.vm.inspect import inspect_vm
    from lightning_sdk.cli.vm.list import list_vms
    from lightning_sdk.cli.vm.ssh import ssh_vm

    group.add_command(create_vm, name="create")
    group.add_command(list_vms, name="list")
    group.add_command(inspect_vm, name="inspect")
    group.add_command(delete_vm, name="delete")
    group.add_command(ssh_vm, name="ssh")
