"""Sandbox command implementations."""

# ruff: noqa: D301

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import click
from rich.table import Table

from lightning_sdk.cli.job.run import _resolve_envs
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.sandbox import RunCommandOpts, Sandbox, SandboxConfig, SandboxInstance, Snapshot


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
        "image": sandbox.image,
        "image_secret_ref": sandbox.image_secret_ref,
        "organization_id": sandbox.organization_id,
        "project_id": sandbox.project_id,
        "ports": sandbox.ports,
        "timeout": sandbox.timeout,
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


def _snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "status": snapshot.status,
        "runtime": snapshot.runtime,
        "runtime_image": snapshot.runtime_image,
        "size_bytes": snapshot.size_bytes,
        "project_id": snapshot.project_id,
        "organization_id": snapshot.organization_id,
        "source_sandbox_id": snapshot.source_sandbox_id,
        "source_sandbox_name": snapshot.source_sandbox_name,
        "source_sandbox_instance_type": snapshot.source_sandbox_instance_type,
        "auto": snapshot.auto,
        "excludes": snapshot.excludes or [],
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        "expires_at": snapshot.expires_at,
    }


def _format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def _snapshot_table(snapshots: Sequence[Snapshot]) -> Table:
    table = Table(pad_edge=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Source sandbox", no_wrap=True)
    table.add_column("Runtime", no_wrap=True)
    table.add_column("Size", no_wrap=True)
    table.add_column("Auto", no_wrap=True)
    for snapshot in snapshots:
        table.add_row(
            snapshot.id,
            snapshot.status,
            snapshot.source_sandbox_name or snapshot.source_sandbox_id,
            snapshot.runtime,
            _format_size(snapshot.size_bytes),
            "yes" if snapshot.auto else "no",
        )
    return table


def _echo_snapshot_summary(snapshot: Snapshot) -> None:
    click.echo(rich_to_str(_snapshot_table([snapshot])), color=True)


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


@click.command("list")
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
    """List sandboxes.

    Example:
      $ sandbox list --teamspace owner/teamspace --limit 2

      Next page token: next-page-token

      $ sandbox list --teamspace owner/teamspace --json

      {
        "total_size": 1
      }
    """
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


@click.command("create")
@_with_common_options
@click.option("--name", help="Sandbox name. Defaults to a generated name.")
@click.option("--instance-type", help="Sandbox instance type. Defaults to cpu-1.")
@click.option("--runtime", help="Runtime image or runtime identifier.")
@click.option("--image", help="Custom OCI image for the sandbox rootfs (mutually exclusive with --runtime).")
@click.option(
    "--image-secret-ref",
    help="Name of a project Docker-registry Secret used to pull a private --image.",
)
@click.option("--spot/--no-spot", default=False, help="Create the sandbox on spot capacity.")
@click.option("--port", "ports", multiple=True, help="Port to expose. Can be passed multiple times.")
@click.option("--teamspace", help="Teamspace to own persistent sandbox state (format: owner/teamspace).")
@click.option("--snapshot-id", help="Snapshot ID to restore from.")
@click.option("--persistent/--ephemeral", "persistent", default=None, help="Persist state across stops.")
@click.option(
    "--timeout",
    type=int,
    help="Maximum sandbox lifetime in milliseconds, after which it is auto-stopped (note: this is ms, "
    "unlike `run --timeout` which is seconds).",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def create_sandbox(
    api_key: str | None,
    name: str | None,
    instance_type: str | None,
    runtime: str | None,
    image: str | None,
    image_secret_ref: str | None,
    spot: bool,
    ports: Sequence[str],
    teamspace: str | None,
    snapshot_id: str | None,
    persistent: bool | None,
    timeout: int | None,
    as_json: bool,
) -> None:
    """Create a sandbox and wait until it is running.

    Example:
      $ sandbox create --name devbox

      devbox

      $ sandbox create --name devbox --teamspace owner/teamspace --persistent

      devbox

      $ sandbox create --name devbox --teamspace owner/teamspace --json

      {
        "persistent": true
      }
    """
    sandbox = _sandbox_client(api_key=api_key).create(
        name=name,
        instance_type=instance_type,
        runtime=runtime,
        image=image,
        image_secret_ref=image_secret_ref,
        spot=spot,
        ports=_parse_ports(ports),
        teamspace=teamspace,
        snapshot_id=snapshot_id,
        persistent=persistent,
        timeout=timeout,
    )
    if as_json:
        _echo_json(_sandbox_to_dict(sandbox))
        return
    _echo_sandbox_summary(sandbox)


@click.command("delete")
@_with_common_options
@click.argument("sandbox_id")
def delete_sandbox(api_key: str | None, sandbox_id: str) -> None:
    """Delete a sandbox.

    Example:
      $ sandbox delete sbx-42

      Deleted sandbox sbx-42
    """
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    sandbox.delete()
    click.echo(f"Deleted sandbox {sandbox_id}")


@click.command("stop")
@_with_common_options
@click.argument("sandbox_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def stop_sandbox(
    api_key: str | None,
    sandbox_id: str,
    as_json: bool,
) -> None:
    """Stop a sandbox.

    Persistent sandboxes may return an automatic snapshot that can be used for
    later resume or restore workflows.

    Example:
      $ sandbox stop sbx-42

      Stopped sandbox sbx-42

      Auto snapshot: snap-abc123

      $ sandbox stop sbx-42 --json

      {
        "auto_snapshot_id": "snap-abc123",
        "id": "sbx-42"
      }
    """
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    auto_snapshot_id = sandbox.stop()
    payload = {"id": sandbox_id, "auto_snapshot_id": auto_snapshot_id}
    if as_json:
        _echo_json(payload)
        return
    click.echo(f"Stopped sandbox {sandbox_id}")
    if auto_snapshot_id:
        click.echo(f"Auto snapshot: {auto_snapshot_id}")


@click.command("start")
@_with_common_options
@click.argument("sandbox_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def start_sandbox(
    api_key: str | None,
    sandbox_id: str,
    as_json: bool,
) -> None:
    """Start a stopped persistent sandbox.

    Example:
      $ sandbox start sbx-42

      devbox
    """
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id).resume()
    if as_json:
        _echo_json(_sandbox_to_dict(sandbox))
        return
    _echo_sandbox_summary(sandbox)


@click.command("update")
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
    """Update a sandbox.

    The backend update route currently supports resuming stopped persistent
    sandboxes. Use `sandbox start` as the shorter lifecycle command.

    Example:
      $ sandbox update sbx-42 --resume

      devbox
    """
    if not resume:
        raise click.UsageError("No update requested. Use --resume to resume a stopped persistent sandbox.")
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id).resume()
    if as_json:
        _echo_json(_sandbox_to_dict(sandbox))
        return
    _echo_sandbox_summary(sandbox)


@click.command(
    "run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@_with_common_options
@click.argument("sandbox_id")
@click.option("--cwd", help="Working directory inside the sandbox.")
@click.option("--env", "env", multiple=True, default=[""], help="Environment variable in KEY=VALUE or JSON format.")
@click.option("--detached", is_flag=True, help="Start the command and return immediately.")
@click.option("--timeout", type=float, help="Seconds to wait for a detached command.")
@click.option("--poll-interval", type=float, default=0.5, show_default=True, help="Detached command poll interval.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
@click.argument("command_args", nargs=-1, required=True)
def run_sandbox_command(
    api_key: str | None,
    sandbox_id: str,
    cwd: str | None,
    env: Sequence[str],
    detached: bool,
    timeout: float | None,
    poll_interval: float,
    as_json: bool,
    command_args: Sequence[str],
) -> None:
    """Run a command in a sandbox.

    Use `--` before the sandbox command when that command has its own flags.

    Examples:
      $ sandbox run sbx-42 -- python -c "print('hello')"

      hello

      $ sandbox run sbx-42 --cwd /workspace --env MODE=test -- python app.py

      app started

      $ sandbox run sbx-42 --detached -- bash -lc "echo start; sleep 1; echo done"

      cmd-abc123

      $ sandbox run sbx-42 --json -- python -c "print('hello')"

      {
        "cmd_id": "cmd-abc123",
        "output": "hello\\n"
      }
    """
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
        click.get_current_context().exit(command.exit_code)


@click.command("logs")
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
    """Show logs for a sandbox command.

    Example:
      $ sandbox logs sbx-42 cmd-abc123

      2026-01-01T12:00:00Z start

      2026-01-01T12:00:01Z done

      $ sandbox logs sbx-42 cmd-abc123 --no-timestamps

      start

      done
    """
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


@click.command("command")
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
    """Show sandbox command status.

    Example:
      $ sandbox command sbx-42 cmd-abc123

      Command ID: cmd-abc123

      Exit code: 0

      done
    """
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
    table.add_row(
        command_id,
        "yes" if status.running else "no",
        exit_code_display,
    )
    click.echo(rich_to_str(table), color=True)
    if status.output:
        click.echo(status.output, nl=not status.output.endswith("\n"))


@click.command("list")
@_with_common_options
@click.option("--name", help="Filter by source sandbox name.")
@click.option("--page-token", help="Pagination token returned by a previous list call.")
@click.option("--limit", type=int, help="Maximum number of snapshots to return.")
@click.option("--teamspace", help="Only list snapshots in this teamspace (format: owner/teamspace).")
@click.option("--sort-order", type=click.Choice(["asc", "desc"]), help="Sort by creation time.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def list_snapshots(
    api_key: str | None,
    name: str | None,
    page_token: str | None,
    limit: int | None,
    teamspace: str | None,
    sort_order: str | None,
    as_json: bool,
) -> None:
    """List sandbox snapshots.

    Example:
      $ sandbox snapshot list --teamspace owner/teamspace --limit 2
      ┏━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┓
      ┃ ID      ┃ Status ┃ Source sandbox ┃ Runtime ┃ Size     ┃ Auto ┃
      ┡━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━┩
      │ snap-42 │ ready  │ devbox         │ python  │ 12.3 MiB │ no   │
      └─────────┴────────┴────────────────┴─────────┴──────────┴──────┘

      $ sandbox snapshot list --teamspace owner/teamspace --json
      {
        "snapshots": [
          {
            "id": "snap-42",
            "status": "ready"
          }
        ],
        "total_size": 1
      }
    """
    result = _sandbox_client(api_key=api_key).list_snapshots(
        name=name,
        page_token=page_token,
        limit=limit,
        teamspace=teamspace,
        sort_order=sort_order,
    )
    if as_json:
        _echo_json(
            {
                "snapshots": [_snapshot_to_dict(snapshot) for snapshot in result.snapshots],
                "next_page_token": result.next_page_token,
                "previous_page_token": result.previous_page_token,
                "total_size": result.total_size,
            }
        )
        return
    click.echo(rich_to_str(_snapshot_table(result.snapshots)), color=True)
    if result.next_page_token:
        click.echo(f"Next page token: {result.next_page_token}")


@click.command("get")
@_with_common_options
@click.argument("snapshot_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def get_snapshot(api_key: str | None, snapshot_id: str, as_json: bool) -> None:
    """Show a sandbox snapshot.

    Example:
      $ sandbox snapshot get snap-42
      ┏━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┓
      ┃ ID      ┃ Status ┃ Source sandbox ┃ Runtime ┃ Size     ┃ Auto ┃
      ┡━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━┩
      │ snap-42 │ ready  │ devbox         │ python  │ 12.3 MiB │ no   │
      └─────────┴────────┴────────────────┴─────────┴──────────┴──────┘
    """
    snapshot = _sandbox_client(api_key=api_key).get_snapshot(snapshot_id)
    if as_json:
        _echo_json(_snapshot_to_dict(snapshot))
        return
    _echo_snapshot_summary(snapshot)


@click.command("create")
@_with_common_options
@click.argument("sandbox_id")
@click.option("--expiration", type=int, help="TTL in milliseconds (0 = never). Defaults to the platform default.")
@click.option("--exclude", "excludes", multiple=True, help="Path to exclude from the snapshot. Repeatable.")
@click.option("--wait/--no-wait", default=True, show_default=True, help="Wait until the snapshot is ready.")
@click.option("--wait-timeout", type=float, default=600.0, show_default=True, help="Seconds to wait for readiness.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def create_snapshot(
    api_key: str | None,
    sandbox_id: str,
    expiration: int | None,
    excludes: Sequence[str],
    wait: bool,
    wait_timeout: float,
    as_json: bool,
) -> None:
    """Snapshot a sandbox's filesystem.

    Captures filesystem state only (not running processes). Waits until the snapshot
    is ready by default; pass --no-wait to return the saving row immediately.

    Example:
      $ sandbox snapshot create sbx-42
      ┏━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┓
      ┃ ID      ┃ Status ┃ Source sandbox ┃ Runtime ┃ Size     ┃ Auto ┃
      ┡━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━┩
      │ snap-42 │ ready  │ devbox         │ python  │ 12.3 MiB │ no   │
      └─────────┴────────┴────────────────┴─────────┴──────────┴──────┘
    """
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    snapshot = sandbox.snapshot(
        expiration=expiration,
        excludes=list(excludes) or None,
        wait=wait,
        wait_timeout=wait_timeout,
    )
    if as_json:
        _echo_json(_snapshot_to_dict(snapshot))
        return
    _echo_snapshot_summary(snapshot)


@click.command("delete")
@_with_common_options
@click.argument("snapshot_id")
def delete_snapshot(api_key: str | None, snapshot_id: str) -> None:
    """Delete a sandbox snapshot.

    Example:
      $ sandbox snapshot delete snap-42
      Deleted snapshot snap-42
    """
    _sandbox_client(api_key=api_key).delete_snapshot(snapshot_id)
    click.echo(f"Deleted snapshot {snapshot_id}")


@click.command("commands")
@_with_common_options
@click.argument("sandbox_id")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def list_sandbox_commands(
    api_key: str | None,
    sandbox_id: str,
    as_json: bool,
) -> None:
    """List a sandbox's command history.

    Example:
      $ sandbox commands sbx-42
      ┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
      ┃ Command ID ┃ Running ┃ Exit code ┃ Command ┃ Started at           ┃
      ┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
      │ cmd-abc123 │ no      │ 0         │ echo    │ 2026-06-19T18:00:47Z │
      └────────────┴─────────┴───────────┴─────────┴──────────────────────┘
    """
    sandbox = _sandbox_client(api_key=api_key).get(sandbox_id)
    cmds = sandbox.list_commands()
    if as_json:
        _echo_json(
            [
                {
                    "cmd_id": c.id,
                    "command": c.command,
                    # Exit code is only meaningful once the command has exited.
                    "exit_code": None if c.running else c.exit_code,
                    "running": c.running,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                }
                for c in cmds
            ]
        )
        return

    table = Table(pad_edge=True)
    table.add_column("Command ID", no_wrap=True)
    table.add_column("Running", no_wrap=True)
    table.add_column("Exit code", no_wrap=True)
    table.add_column("Command")
    table.add_column("Started at", no_wrap=True)
    for c in cmds:
        table.add_row(
            c.id,
            "yes" if c.running else "no",
            "-" if c.running else str(c.exit_code),
            c.command or "-",
            c.started_at.isoformat() if c.started_at else "-",
        )
    click.echo(rich_to_str(table), color=True)
