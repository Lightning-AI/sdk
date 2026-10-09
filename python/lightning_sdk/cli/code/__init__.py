"""code.lightning.ai CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register code.lightning.ai commands with the given group."""
    from lightning_sdk.cli.code.remove import remove
    from lightning_sdk.cli.code.setup import setup
    from lightning_sdk.cli.code.status import status
    from lightning_sdk.cli.code.token import token

    group.add_command(setup)
    group.add_command(status)
    group.add_command(remove)
    group.add_command(token)
