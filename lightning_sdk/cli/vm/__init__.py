import click


def register_commands(group: click.Group) -> None:
    """Register studio commands with the given group."""
    from lightning_sdk.cli.vm.create import create_vm

    group.add_command(create_vm)
