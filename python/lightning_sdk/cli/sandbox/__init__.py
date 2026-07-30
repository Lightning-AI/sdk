"""Sandbox CLI commands."""

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningGroup


@click.group(name="snapshot", cls=LightningGroup)
def snapshot() -> None:
    """Manage Lightning AI Sandbox snapshots.

    A snapshot is an immutable, restorable capture of a sandbox's filesystem.
    Create one from a running sandbox, then restore it via
    `sandbox create --snapshot-id <id>`.

    Examples:
      $ sandbox snapshot create sbx-42
      $ sandbox snapshot list --teamspace owner/teamspace
      $ sandbox snapshot delete snap-42
    """


def register_commands(group: click.Group) -> None:
    """Register sandbox commands with the given group."""
    from lightning_sdk.cli.sandbox.commands import (
        command_status,
        connect_sandbox,
        create_sandbox,
        create_snapshot,
        get_snapshot,
        list_sandbox_commands,
        list_sandboxes,
        list_snapshots,
        logs_sandbox_command,
        resolve_sandbox_delete,
        resolve_snapshot_delete,
        run_sandbox_command,
        start_sandbox,
        stop_sandbox,
        update_sandbox,
    )
    from lightning_sdk.cli.utils.delete import register_delete_command

    group.add_command(list_sandboxes, name="list")
    group.add_command(create_sandbox, name="create")
    group.add_command(update_sandbox, name="update")
    register_delete_command(
        group,
        label="Sandbox",
        help="""Delete a sandbox.

        Example:
          $ sandbox delete sbx-42

          Sandbox deleted
        """,
        identifier="sandbox_id",
        context_option="api_key",
        context_help="Sandbox API key.",
        resolve_delete=resolve_sandbox_delete,
    )
    group.add_command(stop_sandbox, name="stop")
    group.add_command(start_sandbox, name="start")
    group.add_command(connect_sandbox, name="connect")
    group.add_command(run_sandbox_command, name="run")
    group.add_command(logs_sandbox_command, name="logs")
    group.add_command(command_status, name="command")

    snapshot.add_command(list_snapshots, name="list")
    snapshot.add_command(get_snapshot, name="get")
    snapshot.add_command(create_snapshot, name="create")
    register_delete_command(
        snapshot,
        label="Snapshot",
        help="""Delete a sandbox snapshot.

        Example:
          $ sandbox snapshot delete snap-42

          Snapshot deleted
        """,
        identifier="snapshot_id",
        context_option="api_key",
        context_help="Sandbox API key.",
        resolve_delete=resolve_snapshot_delete,
    )
    group.add_command(snapshot, name="snapshot")
    group.add_command(list_sandbox_commands, name="commands")
