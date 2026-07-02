from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.sandbox import commands as sandbox_commands
from tests.cli.help import assert_help_contains, mock_command_logging


@dataclass
class FakeSandboxInstance:
    sandbox_id: str = "sbx-1"
    name: str = "unit-sandbox"
    status: str = "running"
    instance_type: str = "cpu-1"
    spot: bool = False
    persistent: bool = True
    runtime: str = "python"
    organization_id: str = "org-1"
    project_id: str = "proj-1"
    cluster_id: str = "cluster-1"
    cloudspace_id: str = ""
    ports: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.ports is None:
            self.ports = ["8888"]
        if self.created_at is None:
            self.created_at = datetime(2026, 1, 1, 12, 0, 0)
        if self.updated_at is None:
            self.updated_at = datetime(2026, 1, 1, 12, 1, 0)
        self.deleted = False
        self.stopped = False
        self.resumed = False
        self.last_command = None

    def delete(self) -> None:
        self.deleted = True

    def stop(self) -> str:
        self.stopped = True
        return "snap-1"

    def resume(self) -> FakeSandboxInstance:
        self.resumed = True
        return self

    def run_command(self, opts):
        self.last_command = opts
        return SimpleNamespace(
            cmd_id="cmd-1",
            output="hello\n",
            exit_code=0 if opts.cmd != "false" else 7,
            running=False,
            wait=lambda **_: None,
        )

    def get_command_logs(self, command_id: str):
        return [
            SimpleNamespace(timestamp="2026-01-01T12:00:00Z", message=f"{command_id}: start"),
            SimpleNamespace(timestamp="2026-01-01T12:00:01Z", message=f"{command_id}: done"),
        ]

    def get_command(self, command_id: str):
        return SimpleNamespace(output=f"{command_id}: output\n", exit_code=0, running=False)

    def snapshot(self, **kwargs):
        self.snapshot_kwargs = kwargs
        return FakeSnapshot()


@dataclass
class FakeSnapshot:
    id: str = "snap-1"
    status: str = "ready"
    runtime: str = "python"
    runtime_image: str = "python:3.11"
    size_bytes: int = 12_900_000
    project_id: str = "proj-1"
    organization_id: str = "org-1"
    source_sandbox_id: str = "sbx-1"
    source_sandbox_name: str = "unit-sandbox"
    source_sandbox_instance_type: str = "cpu-1"
    auto: bool = False
    excludes: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime(2026, 1, 1, 12, 0, 0)
        if self.updated_at is None:
            self.updated_at = datetime(2026, 1, 1, 12, 1, 0)


class FakeSandboxClient:
    def __init__(self, instance: FakeSandboxInstance | None = None) -> None:
        self.instance = instance or FakeSandboxInstance()
        self.create_kwargs = None
        self.list_kwargs = None
        self.get_ids: list[str] = []
        self.list_snapshots_kwargs = None
        self.get_snapshot_ids: list[str] = []
        self.deleted_snapshot_ids: list[str] = []

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return SimpleNamespace(
            sandboxes=[self.instance],
            next_page_token="next",
            previous_page_token="prev",
            total_size=1,
        )

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return self.instance

    def get(self, sandbox_id: str):
        self.get_ids.append(sandbox_id)
        return self.instance

    def list_snapshots(self, **kwargs):
        self.list_snapshots_kwargs = kwargs
        return SimpleNamespace(
            snapshots=[FakeSnapshot()],
            next_page_token="next-snap",
            previous_page_token="prev-snap",
            total_size=1,
        )

    def get_snapshot(self, snapshot_id: str):
        self.get_snapshot_ids.append(snapshot_id)
        return FakeSnapshot(id=snapshot_id)

    def delete_snapshot(self, snapshot_id: str) -> None:
        self.deleted_snapshot_ids.append(snapshot_id)


def _invoke(args: list[str]) -> SimpleNamespace:
    runner = CliRunner()
    result = runner.invoke(main_cli, args, catch_exceptions=False)
    return SimpleNamespace(exit_code=result.exit_code, output=result.output)


@mock_command_logging
def test_sandbox_help() -> None:
    assert_help_contains(
        "lightning sandbox --help",
        "Usage: lightning sandbox",
        "Ephemeral sandboxes for agents.",
        "https://lightning.ai by default; set LIGHTNING_CLOUD_URL to",
        "$ sandbox create --name devbox --teamspace owner/teamspace --persistent",
        "$ sandbox run sbx-42 -- python -c \"print('hello')\"",
        "Auto snapshot: snap-abc123",
        "create",
        "delete",
        "logs",
        "run",
    )


@mock_command_logging
def test_sandboxes_plural_alias_help() -> None:
    assert_help_contains("lightning sandboxes --help", "Usage: lightning sandboxes", "Ephemeral sandboxes for agents.")


@mock_command_logging
def test_sandbox_command_help_examples() -> None:
    list_help = assert_help_contains(
        "lightning sandbox list --help",
        "$ sandbox list --teamspace owner/teamspace --limit 2",
        "Next page token: next-page-token",
        '"total_size": 1',
    )
    assert "Cluster" not in list_help
    assert_help_contains(
        "lightning sandbox create --help",
        "$ sandbox create --name devbox --teamspace owner/teamspace --persistent",
        '"persistent": true',
    )
    assert_help_contains(
        "lightning sandbox run --help",
        '$ sandbox run sbx-42 --detached -- bash -lc "echo start; sleep 1; echo done"',
        "cmd-abc123",
        '"output": "hello\\n"',
    )
    assert_help_contains(
        "lightning sandbox logs --help",
        "$ sandbox logs sbx-42 cmd-abc123 --no-timestamps",
        "start",
        "done",
    )
    assert_help_contains(
        "lightning sandbox command --help",
        "$ sandbox command sbx-42 cmd-abc123",
        "Command ID",
        "Exit code",
    )
    assert_help_contains(
        "lightning sandbox stop --help",
        "$ sandbox stop sbx-42 --json",
        '"auto_snapshot_id": "snap-abc123"',
    )
    assert_help_contains("lightning sandbox start --help", "$ sandbox start sbx-42", "devbox")
    assert_help_contains("lightning sandbox update --help", "$ sandbox update sbx-42 --resume", "devbox")
    assert_help_contains("lightning sandbox delete --help", "$ sandbox delete sbx-42", "Deleted sandbox sbx-42")


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_list(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "list", "--limit", "5", "--page-token", "abc"])

    assert result.exit_code == 0
    assert "sbx-1" in result.output
    assert "Cluster" not in result.output
    assert "cluster-1" not in result.output
    assert "Next page token: next" in result.output
    assert client.list_kwargs == {"page_token": "abc", "limit": 5, "teamspace": None}


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_list_forwards_teamspace(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "list", "--teamspace", "owner/teamspace"])

    assert result.exit_code == 0
    assert client.list_kwargs == {"page_token": None, "limit": None, "teamspace": "owner/teamspace"}


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_create_forwards_options(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(
        [
            "sandbox",
            "create",
            "--name",
            "cli-sandbox",
            "--instance-type",
            "cpu-1",
            "--runtime",
            "python",
            "--spot",
            "--port",
            "8888",
            "--port",
            "http",
            "--teamspace",
            "owner/teamspace",
            "--snapshot-id",
            "snap-0",
            "--persistent",
            "--timeout",
            "3600000",
        ]
    )

    assert result.exit_code == 0
    assert client.create_kwargs == {
        "name": "cli-sandbox",
        "instance_type": "cpu-1",
        "runtime": "python",
        "image": None,
        "image_secret_ref": None,
        "spot": True,
        "ports": [8888, "http"],
        "teamspace": "owner/teamspace",
        "snapshot_id": "snap-0",
        "persistent": True,
        "timeout": 3600000,
    }


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_lifecycle_commands(_mock_log_command, monkeypatch) -> None:
    instance = FakeSandboxInstance()
    client = FakeSandboxClient(instance)
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    assert _invoke(["sandbox", "stop", "sbx-1"]).exit_code == 0
    assert instance.stopped is True

    assert _invoke(["sandbox", "start", "sbx-1"]).exit_code == 0
    assert instance.resumed is True

    assert _invoke(["sandbox", "delete", "sbx-1"]).exit_code == 0
    assert instance.deleted is True
    assert client.get_ids == ["sbx-1", "sbx-1", "sbx-1"]


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_update_requires_resume(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = CliRunner().invoke(main_cli, ["sandbox", "update", "sbx-1"])

    assert result.exit_code != 0
    assert "Use --resume" in result.output


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_update_resume(_mock_log_command, monkeypatch) -> None:
    instance = FakeSandboxInstance()
    client = FakeSandboxClient(instance)
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "update", "sbx-1", "--resume"])

    assert result.exit_code == 0
    assert instance.resumed is True


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_run_command(_mock_log_command, monkeypatch) -> None:
    instance = FakeSandboxInstance()
    client = FakeSandboxClient(instance)
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(
        [
            "sandbox",
            "run",
            "sbx-1",
            "--cwd",
            "/tmp",
            "--env",
            "A=b",
            "--",
            "python",
            "-c",
            "print('hello')",
        ]
    )

    assert result.exit_code == 0
    assert result.output == "hello\n"
    assert instance.last_command.cmd == "python"
    assert instance.last_command.args == ["-c", "print('hello')"]
    assert instance.last_command.cwd == "/tmp"
    assert instance.last_command.env == {"A": "b"}


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_run_command_uses_exit_code(_mock_log_command, monkeypatch) -> None:
    instance = FakeSandboxInstance()
    client = FakeSandboxClient(instance)
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = CliRunner().invoke(main_cli, ["sandbox", "run", "sbx-1", "--", "false"])

    assert result.exit_code == 7
    assert "hello" in result.output


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_logs_and_command_status(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    logs = _invoke(["sandbox", "logs", "sbx-1", "cmd-1", "--no-timestamps"])
    assert logs.exit_code == 0
    assert "cmd-1: start" in logs.output
    assert "cmd-1: done" in logs.output

    status = _invoke(["sandbox", "command", "sbx-1", "cmd-1"])
    assert status.exit_code == 0
    assert "cmd-1" in status.output
    assert "cmd-1: output" in status.output


@mock_command_logging
def test_sandbox_snapshot_help() -> None:
    assert_help_contains(
        "lightning sandbox snapshot --help",
        "Usage: lightning sandbox snapshot",
        "Manage Lightning AI Sandbox snapshots.",
        "create",
        "delete",
        "get",
        "list",
    )


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_snapshot_list(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(
        ["sandbox", "snapshot", "list", "--teamspace", "owner/teamspace", "--sort-order", "desc", "--limit", "5"]
    )

    assert result.exit_code == 0
    assert "snap-1" in result.output
    assert "Next page token: next-snap" in result.output
    assert client.list_snapshots_kwargs == {
        "name": None,
        "page_token": None,
        "limit": 5,
        "teamspace": "owner/teamspace",
        "sort_order": "desc",
    }


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_snapshot_list_json(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "snapshot", "list", "--json"])

    assert result.exit_code == 0
    assert '"id": "snap-1"' in result.output
    assert '"total_size": 1' in result.output


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_snapshot_get(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "snapshot", "get", "snap-9"])

    assert result.exit_code == 0
    assert "snap-9" in result.output
    assert client.get_snapshot_ids == ["snap-9"]


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_snapshot_create(_mock_log_command, monkeypatch) -> None:
    instance = FakeSandboxInstance()
    client = FakeSandboxClient(instance)
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "snapshot", "create", "sbx-1", "--expiration", "0", "--exclude", "/tmp", "--no-wait"])

    assert result.exit_code == 0
    assert "snap-1" in result.output
    assert client.get_ids == ["sbx-1"]
    assert instance.snapshot_kwargs == {
        "expiration": 0,
        "excludes": ["/tmp"],
        "wait": False,
        "wait_timeout": 600.0,
    }


@mock.patch("lightning_sdk.cli.utils.logging._log_command")
@mock_command_logging
def test_sandbox_snapshot_delete(_mock_log_command, monkeypatch) -> None:
    client = FakeSandboxClient()
    monkeypatch.setattr(sandbox_commands, "_sandbox_client", lambda **_: client)

    result = _invoke(["sandbox", "snapshot", "delete", "snap-9"])

    assert result.exit_code == 0
    assert "Deleted snapshot snap-9" in result.output
    assert client.deleted_snapshot_ids == ["snap-9"]
