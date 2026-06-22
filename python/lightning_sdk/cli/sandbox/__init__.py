"""Sandbox CLI commands."""

import click


@click.group(name="snapshot")
def snapshot() -> None:
    r"""Manage Lightning AI Sandbox snapshots.

    A snapshot is an immutable, restorable capture of a sandbox's filesystem.
    Create one from a running sandbox, then restore it via
    `sandbox create --snapshot-id <id>`.

    \b
    Examples:
      $ sandbox snapshot create sbx-42
      $ sandbox snapshot list --teamspace owner/teamspace
      $ sandbox snapshot delete snap-42
    """


def register_commands(group: click.Group) -> None:
    """Register sandbox commands with the given group."""
    from lightning_sdk.cli.sandbox.commands import (
        command_status,
        create_sandbox,
        create_snapshot,
        delete_sandbox,
        delete_snapshot,
        get_snapshot,
        list_sandbox_commands,
        list_sandboxes,
        list_snapshots,
        logs_sandbox_command,
        run_sandbox_command,
        start_sandbox,
        stop_sandbox,
        update_sandbox,
    )

    group.add_command(list_sandboxes, name="list")
    group.add_command(create_sandbox, name="create")
    group.add_command(update_sandbox, name="update")
    group.add_command(delete_sandbox, name="delete")
    group.add_command(stop_sandbox, name="stop")
    group.add_command(start_sandbox, name="start")
    group.add_command(run_sandbox_command, name="run")
    group.add_command(logs_sandbox_command, name="logs")
    group.add_command(command_status, name="command")

    snapshot.add_command(list_snapshots, name="list")
    snapshot.add_command(get_snapshot, name="get")
    snapshot.add_command(create_snapshot, name="create")
    snapshot.add_command(delete_snapshot, name="delete")
    group.add_command(snapshot, name="snapshot")
    group.add_command(list_sandbox_commands, name="commands")
