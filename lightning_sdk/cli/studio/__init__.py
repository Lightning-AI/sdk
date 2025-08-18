"""Studio CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register studio commands with the given group."""
    from lightning_sdk.cli.studio.create import create_studio
    from lightning_sdk.cli.studio.delete import delete_studio
    from lightning_sdk.cli.studio.list import list_studios
    from lightning_sdk.cli.studio.ssh import ssh_studio
    from lightning_sdk.cli.studio.start import start_studio
    from lightning_sdk.cli.studio.stop import stop_studio
    from lightning_sdk.cli.studio.switch import switch_studio

    group.add_command(delete_studio)
    group.add_command(create_studio)
    group.add_command(list_studios)
    group.add_command(ssh_studio)
    group.add_command(start_studio)
    group.add_command(stop_studio)
    group.add_command(switch_studio)
