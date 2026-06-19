"""Sandbox command implementations."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import click
from rich.table import Table

from lightning_sdk.cli.job.run import _resolve_envs
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.sandbox import RunCommandOpts, Sandbox, SandboxConfig, SandboxInstance


def _sandbox_config(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> SandboxConfig:
    env_config = SandboxConfig.from_env()
    return env_config.merge(SandboxConfig(api_key=api_key, base_url=base_url))


def _sandbox_client(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Sandbox:
    return Sandbox(_sandbox_config(api_key=api_key, base_url=base_url))


def _json_default(value: object) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[attr-defined]
    return str(value)


def _sandbox_to_dict(sandbox: SandboxInstance) -> dict[str, Any]:
    return {
        "id": sandbox.sandbox_id,
        "name": sandbox.name,
        "status": sandbox.status,
        "instance_type": sandbox.instance_type,
        "spot": sandbox.spot,
        "persistent": sandbox.persistent,
        "runtime": sandbox.runtime or "",
        "organization_id": sandbox.organization_id,
        "project_id": sandbox.project_id,
        "cluster_id": sandbox.cluster_id,
        "cloudspace_id": sandbox.cloudspace_id,
        "ports": sandbox.ports,
        "created_at": sandbox.created_at,
        "updated_at": sandbox.updated_at,
    }


def _echo_json(payload: object) -> None:
    click.echo(json.dumps(payload, default=_json_default, indent=2, sort_keys=True))


def _echo_sandbox_summary(sandbox: SandboxInstance) -> None:
    table = Table(pad_edge=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Instance type", no_wrap=True)
    table.add_column("Persistent", no_wrap=True)
    table.add_column("Cluster", no_wrap=True)
    table.add_row(
        sandbox.sandbox_id,
        sandbox.name,
        sandbox.status,
        sandbox.instance_type,
        "yes" if sandbox.persistent else "no",
        sandbox.cluster_id,
    )
    click.echo(rich_to_str(table), color=True)


def _parse_env(env: Sequence[str]) -> dict[str, str]:
    env_dict: dict[str, str] = {}
    for value in env:
        env_dict.update(_resolve_envs(value))
    return env_dict


def _parse_ports(ports: Sequence[str]) -> list[int | str]:
    parsed: list[int | str] = []
    for port in ports:
        try:
            parsed.append(int(port))
        except ValueError:
            parsed.append(port)
    return parsed


COMMON_OPTIONS = [
    click.option("--api-key", envvar="LIGHTNING_SANDBOX_API_KEY", help="Sandbox API key."),
]


def _with_common_options(command: click.Command) -> click.Command:
    for option in reversed(COMMON_OPTIONS):
        command = option(command)
    return command


_LIST_SANDBOXES_HELP = """List sandboxes.

\b
Example:
  $ sandbox list --teamspace owner/teamspace --limit 2
  ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
  ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃
  ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
  │ sbx-42 │ devbox │ running │ cpu-small     │ yes        │
  └────────┴────────┴─────────┴───────────────┴────────────┘
  Next page token: next-page-token

\b
  $ sandbox list --teamspace owner/teamspace --json
  {
    "sandboxes": [
      {
        "id": "sbx-42",
        "name": "devbox",
        "status": "running"
      }
    ],
    "total_size": 1
  }
"""


_CREATE_SANDBOX_HELP = """Create a sandbox and wait until it is running.

\b
Example:
  $ sandbox create --name devbox --teamspace owner/teamspace --persistent
  ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
  ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃ Cluster   ┃
  ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
  │ sbx-42 │ devbox │ running │ cpu-small     │ yes        │ aws-use1  │
  └────────┴────────┴─────────┴───────────────┴────────────┴───────────┘

\b
  $ sandbox create --name devbox --teamspace owner/teamspace --json
  {
    "id": "sbx-42",
    "name": "devbox",
    "status": "running",
    "persistent": true
  }
"""


_DELETE_SANDBOX_HELP = """Delete a sandbox.

\b
Example:
  $ sandbox delete sbx-42
  Deleted sandbox sbx-42
"""


_STOP_SANDBOX_HELP = """Stop a sandbox.

Persistent sandboxes may return an automatic snapshot that can be used for
later resume or restore workflows.

\b
Example:
  $ sandbox stop sbx-42
  Stopped sandbox sbx-42
  Auto snapshot: snap-abc123

\b
  $ sandbox stop sbx-42 --json
  {
    "auto_snapshot_id": "snap-abc123",
    "id": "sbx-42"
  }
"""


_START_SANDBOX_HELP = """Start a stopped persistent sandbox.

\b
Example:
  $ sandbox start sbx-42
  ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
  ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃ Cluster   ┃
  ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
  │ sbx-42 │ devbox │ running │ cpu-small     │ yes        │ aws-use1  │
  └────────┴────────┴─────────┴───────────────┴────────────┴───────────┘
"""


_UPDATE_SANDBOX_HELP = """Update a sandbox.

The backend update route currently supports resuming stopped persistent
sandboxes. Use `sandbox start` as the shorter lifecycle command.

\b
Example:
  $ sandbox update sbx-42 --resume
  ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
  ┃ ID     ┃ Name   ┃ Status  ┃ Instance type ┃ Persistent ┃ Cluster   ┃
  ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
  │ sbx-42 │ devbox │ running │ cpu-small     │ yes        │ aws-use1  │
  └────────┴────────┴─────────┴───────────────┴────────────┴───────────┘
"""


_RUN_SANDBOX_COMMAND_HELP = """Run a command in a sandbox.

Use `--` before the sandbox command when that command has its own flags.

\b
Examples:
  $ sandbox run sbx-42 -- python -c "print('hello')"
  hello

\b
  $ sandbox run sbx-42 --cwd /workspace --env MODE=test -- python app.py
  app started

\b
  $ sandbox run sbx-42 --detached -- bash -lc "echo start; sleep 1; echo done"
  cmd-abc123

\b
  $ sandbox run sbx-42 --json -- python -c "print('hello')"
  {
    "cmd_id": "cmd-abc123",
    "exit_code": 0,
    "output": "hello\\n",
    "running": false,
    "sandbox_id": "sbx-42"
  }
"""


_LOGS_SANDBOX_COMMAND_HELP = """Show logs for a sandbox command.

\b
Example:
  $ sandbox logs sbx-42 cmd-abc123
  2026-01-01T12:00:00Z start
  2026-01-01T12:00:01Z done

\b
  $ sandbox logs sbx-42 cmd-abc123 --no-timestamps
  start
  done
"""


_COMMAND_STATUS_HELP = """Show sandbox command status.

\b
Example:
  $ sandbox command sbx-42 cmd-abc123
  ┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┓
  ┃ Command ID ┃ Running ┃ Exit code ┃
  ┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━┩
  │ cmd-abc123 │ no      │ 0         │
  └────────────┴─────────┴───────────┘
  done
"""


@click.command("list", help=_LIST_SANDBOXES_HELP)
@_with_common_options
@click.option("--page-token", help="Pagination token returned by a previous list call.")
@click.option("--limit", type=int, help="Maximum number of sandboxes to return.")
@click.option("--teamspace", help="Only list sandboxes in this teamspace (format: owner/teamspace).")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def list_sandboxes(
    api_key: str | None,
    page_token: str | None,
    limit: int | None,
    teamspace: str | None,
    as_json: bool,
) -> None:
    """List sandboxes."""
    result = _sandbox_client(api_key=api_key).list(
        page_token=page_token,
        limit=limit,
        teamspace=teamspace,
    )

    if as_json:
        _echo_json(
            {
                "sandboxes": [_sandbox_to_dict(sandbox) for sandbox in result.sandboxes],
                "next_page_token": result.next_page_token,
                "previous_page_token": result.previous_page_token,
                "total_size": result.total_size,
            }
        )
        return

    table = Table(pad_edge=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Instance type", no_wrap=True)
    table.add_column("Persistent", no_wrap=True)

    for sandbox in result.sandboxes:
        table.add_row(
            sandbox.sandbox_id,
            sandbox.name,
            sandbox.status,
            sandbox.instance_type,
            "yes" if sandbox.persistent else "no",
        )

    click.echo(rich_to_str(table), color=True)
    if result.next_page_token:
        click.echo(f"Next page token: {result.next_page_token}")


@click.command("create", help=_CREATE_SANDBOX_HELP)
@_with_common_options
@click.option("--name", help="Sandbox name. Defaults to a generated name.")
@click.option("--instance-type", help="Sandbox instance type. Defaults to cpu-small.")
@click.option("--runtime", help="Runtime image or runtime identifier.")
@click.option("--spot/--no-spot", default=False, help="Create the sandbox on spot capacity.")
@click.option("--port", "ports", multiple=True, help="Port to expose. Can be passed multiple times.")
@click.option("--teamspace", help="Teamspace to own persistent sandbox state (format: owner/teamspace).")
@click.option("--snapshot-id", help="Snapshot ID to restore from.")
@click.option("--persistent/--ephemeral", "persistent", default=None, help="Persist state across stops.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def create_sandbox(
    api_key: str | None,
    name: str | None,
    instance_type: str | None,
    runtime: str | None,
    spot: bool,
    ports: Sequence[str],
    teamspace: str | None,
    snapshot_id: str | None,
    persistent: bool | None,
    as_json: bool,
) -> None:
    """Create a sandbox and wait until it is running."""
    sandbox = _sandbox_client(api_key=api_key).create(
        name=name,
        instance_type=instance_type,
        runtime=runtime,
        spot=spot,
        ports=_parse_ports(ports),
        teamspace=teamspace,
        snapshot_id=snapshot_id,
        persistent=persistent,
    )
    if as_json:
        _echo_json(_sandbox_to_dict(sandbox))
        return
    _echo_sandbox_summary(sandbox)


@click.command("delete", help=_DELETE_SANDBOX_HELP)
@_with_common_options
@click.argument("sandbox_id")
def delete_sandbox(api_key: str | None, sandbox_id: str) -> None:
    """Delete a sandbox."""
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    sandbox.delete()
    click.echo(f"Deleted sandbox {sandbox_id}")


@click.command("stop", help=_STOP_SANDBOX_HELP)
@_with_common_options
@click.argument("sandbox_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def stop_sandbox(
    api_key: str | None,
    sandbox_id: str,
    as_json: bool,
) -> None:
    """Stop a sandbox."""
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    auto_snapshot_id = sandbox.stop()
    payload = {"id": sandbox_id, "auto_snapshot_id": auto_snapshot_id}
    if as_json:
        _echo_json(payload)
        return
    click.echo(f"Stopped sandbox {sandbox_id}")
    if auto_snapshot_id:
        click.echo(f"Auto snapshot: {auto_snapshot_id}")


@click.command("start", help=_START_SANDBOX_HELP)
@_with_common_options
@click.argument("sandbox_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def start_sandbox(
    api_key: str | None,
    sandbox_id: str,
    as_json: bool,
) -> None:
    """Start a stopped persistent sandbox."""
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id).resume()
    if as_json:
        _echo_json(_sandbox_to_dict(sandbox))
        return
    _echo_sandbox_summary(sandbox)


@click.command("update", help=_UPDATE_SANDBOX_HELP)
@_with_common_options
@click.argument("sandbox_id")
@click.option("--resume", is_flag=True, help="Resume a stopped persistent sandbox.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def update_sandbox(
    api_key: str | None,
    sandbox_id: str,
    resume: bool,
    as_json: bool,
) -> None:
    """Update a sandbox."""
    if not resume:
        raise click.UsageError("No update requested. Use --resume to resume a stopped persistent sandbox.")
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id).resume()
    if as_json:
        _echo_json(_sandbox_to_dict(sandbox))
        return
    _echo_sandbox_summary(sandbox)


@click.command(
    "run",
    help=_RUN_SANDBOX_COMMAND_HELP,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@_with_common_options
@click.argument("sandbox_id")
@click.option("--cwd", help="Working directory inside the sandbox.")
@click.option("--env", "env", multiple=True, default=[""], help="Environment variable in KEY=VALUE or JSON format.")
@click.option("--sudo", is_flag=True, help="Run the command with sudo.")
@click.option("--detached", is_flag=True, help="Start the command and return immediately.")
@click.option("--timeout", type=float, help="Seconds to wait for a detached command.")
@click.option("--poll-interval", type=float, default=0.5, show_default=True, help="Detached command poll interval.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
@click.argument("command_args", nargs=-1, required=True)
@click.pass_context
def run_sandbox_command(
    ctx: click.Context,
    api_key: str | None,
    sandbox_id: str,
    cwd: str | None,
    env: Sequence[str],
    sudo: bool,
    detached: bool,
    timeout: float | None,
    poll_interval: float,
    as_json: bool,
    command_args: Sequence[str],
) -> None:
    """Run a command in a sandbox."""
    command_parts = list(command_args)
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        raise click.UsageError("Missing command to run.")

    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    command = sandbox.run_command(
        RunCommandOpts(
            cmd=command_parts[0],
            args=command_parts[1:],
            cwd=cwd,
            env=_parse_env(env),
            sudo=sudo or None,
            detached=detached,
        )
    )
    if detached and timeout is not None:
        command.wait(timeout=timeout, poll_interval=poll_interval)

    payload = {
        "sandbox_id": sandbox_id,
        "cmd_id": command.cmd_id,
        "output": command.output,
        "exit_code": command.exit_code,
        "running": command.running,
    }
    if as_json:
        _echo_json(payload)
    else:
        if detached and command.running:
            click.echo(command.cmd_id)
        elif command.output:
            click.echo(command.output, nl=not command.output.endswith("\n"))
        if command.cmd_id and (detached or not command.output):
            click.echo(f"Command ID: {command.cmd_id}")

    if command.exit_code not in (None, 0):
        ctx.exit(command.exit_code)


@click.command("logs", help=_LOGS_SANDBOX_COMMAND_HELP)
@_with_common_options
@click.argument("sandbox_id")
@click.argument("command_id")
@click.option("--no-timestamps", is_flag=True, help="Only print log messages.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def logs_sandbox_command(
    api_key: str | None,
    sandbox_id: str,
    command_id: str,
    no_timestamps: bool,
    as_json: bool,
) -> None:
    """Show logs for a sandbox command."""
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    logs = sandbox.get_command_logs(command_id)
    payload = [{"timestamp": log.timestamp, "message": log.message} for log in logs]
    if as_json:
        _echo_json(payload)
        return
    for log in logs:
        if no_timestamps:
            click.echo(log.message)
        else:
            click.echo(f"{log.timestamp} {log.message}".strip())


@click.command("command", help=_COMMAND_STATUS_HELP)
@_with_common_options
@click.argument("sandbox_id")
@click.argument("command_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def command_status(
    api_key: str | None,
    sandbox_id: str,
    command_id: str,
    as_json: bool,
) -> None:
    """Show sandbox command status."""
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    status = sandbox.get_command(command_id)
    payload = {
        "sandbox_id": sandbox_id,
        "cmd_id": command_id,
        "output": status.output,
        # Only report an exit code once the command has exited (matches `run`).
        "exit_code": None if status.running else status.exit_code,
        "running": status.running,
    }
    if as_json:
        _echo_json(payload)
        return

    table = Table(pad_edge=True)
    table.add_column("Command ID", no_wrap=True)
    table.add_column("Running", no_wrap=True)
    table.add_column("Exit code", no_wrap=True)
    # The exit code is only meaningful once the command has exited; show "-"
    # while it is still running so a default 0 does not read as "succeeded".
    exit_code_display = "-" if status.running else str(status.exit_code)
    table.add_row(command_id, "yes" if status.running else "no", exit_code_display)
    click.echo(rich_to_str(table), color=True)
    if status.output:
        click.echo(status.output, nl=not status.output.endswith("\n"))
