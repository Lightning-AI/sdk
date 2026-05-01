import click


def register_commands(group: click.Group) -> None:
    """Register studio commands with the given group."""
    from lightning_sdk.cli.vm.create import create_vm
    from lightning_sdk.cli.vm.delete import delete_vm
    from lightning_sdk.cli.vm.list import list_vms
    from lightning_sdk.cli.vm.ssh import ssh_vm
    from lightning_sdk.cli.vm.start import start_vm
    from lightning_sdk.cli.vm.stop import stop_vm
    from lightning_sdk.cli.vm.switch import switch_vm

    group.add_command(create_vm)
    group.add_command(delete_vm)
    group.add_command(list_vms)
    group.add_command(ssh_vm)
    group.add_command(start_vm)
    group.add_command(stop_vm)
    group.add_command(switch_vm)
