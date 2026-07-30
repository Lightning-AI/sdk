"""MMT CLI commands."""

import rich_click as click


def register_commands(group: click.Group) -> None:
    """Register MMT commands with the given group."""
    from lightning_sdk.cli.utils.delete import register_delete_command
    from lightning_sdk.cli.mmt.inspect import inspect_mmt
    from lightning_sdk.cli.mmt.list import list_mmts
    from lightning_sdk.cli.mmt.logs import logs_mmt
    from lightning_sdk.cli.mmt.run import run_mmt
    from lightning_sdk.cli.mmt.ssh import ssh_mmt
    from lightning_sdk.cli.mmt.stop import stop_mmt
    from lightning_sdk.mmt import MMT

    group.add_command(run_mmt, name="run")
    group.add_command(list_mmts, name="list")
    group.add_command(inspect_mmt, name="inspect")
    group.add_command(logs_mmt, name="logs")
    group.add_command(ssh_mmt, name="ssh")
    group.add_command(stop_mmt, name="stop")
    register_delete_command(
        group,
        MMT,
        label="Multi-machine job",
        help="Delete a multi-machine job.",
        context_help="Override default teamspace (format: owner/teamspace).",
    )
