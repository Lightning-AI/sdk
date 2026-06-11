"""Sandbox CLI commands."""

import click


def register_commands(group: click.Group) -> None:
    """Register sandbox commands with the given group."""
    from lightning_sdk.cli.sandbox.commands import (
        command_status,
        create_sandbox,
        delete_sandbox,
        list_sandboxes,
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
