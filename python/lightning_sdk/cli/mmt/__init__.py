"""MMT CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register MMT commands with the given group."""
    from lightning_sdk.cli.mmt.delete import delete_mmt
    from lightning_sdk.cli.mmt.inspect import inspect_mmt
    from lightning_sdk.cli.mmt.list import list_mmts
    from lightning_sdk.cli.mmt.run import run_mmt
    from lightning_sdk.cli.mmt.stop import stop_mmt

    group.add_command(run_mmt, name="run")
    group.add_command(list_mmts, name="list")
    group.add_command(inspect_mmt, name="inspect")
    group.add_command(stop_mmt, name="stop")
    group.add_command(delete_mmt, name="delete")
