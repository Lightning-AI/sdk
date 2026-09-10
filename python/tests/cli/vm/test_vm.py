import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import click
from click.testing import CliRunner

from lightning_sdk.cli.vm import register_commands
from lightning_sdk.cli.vm.create import create_vm
from lightning_sdk.cli.vm.inspect import inspect_vm
from lightning_sdk.cli.vm.list import list_vms
from lightning_sdk.cli.vm.ssh import ssh_vm
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.user import User
from tests.cli.help import assert_help_contains, mock_command_logging


def _plain(output: str) -> str:
    return " ".join(output.split())


def _teamspace() -> SimpleNamespace:
    return SimpleNamespace(id="ts-1", name="research", owner=SimpleNamespace(id="org-1", name="ecorp"))


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_BOX_RE = re.compile(r"[\u2500-\u257f]")


def _flat(output: str) -> str:
    text = _ANSI_RE.sub("", output)
    text = _BOX_RE.sub(" ", text)
    return " ".join(text.split())


@mock_command_logging
def test_vm_help() -> None:
    assert_help_contains(
        "lightning vm --help",
        "Usage: lightning vm [OPTIONS] COMMAND [ARGS]...",
        "Create and manage virtual machines.",
        "create",
        "delete",
        "inspect",
        "list",
        "ssh",
    )


@mock_command_logging
def test_create_prints_id_and_status(monkeypatch) -> None:
    vm = SimpleNamespace(id="vm-1", name="sim-1", status="pending", ssh_command=None)
    create = MagicMock(return_value=vm)
    monkeypatch.setattr("lightning_sdk.cli.vm.create.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.create.VM", SimpleNamespace(create=create))

    result = CliRunner().invoke(create_vm, ["sim-1", "--machine", "H100", "--volume-size", "500"])

    assert result.exit_code == 0, result.output
    assert "vm-1" in result.output
    assert "pending" in result.output
    kwargs = create.call_args.kwargs
    assert kwargs["name"] == "sim-1"
    assert kwargs["machine"].name == "H100"
    assert kwargs["volume_size"] == 500
    assert kwargs["wait"] is False


@mock_command_logging
def test_create_wait_prints_ssh_command(monkeypatch) -> None:
    vm = SimpleNamespace(id="vm-1", name="sim-1", status="running", ssh_command="ssh -p 20032 ubuntu@1.2.3.4")
    create = MagicMock(return_value=vm)
    monkeypatch.setattr("lightning_sdk.cli.vm.create.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.create.VM", SimpleNamespace(create=create))

    result = CliRunner().invoke(create_vm, ["sim-1", "--machine", "H100", "--wait", "--timeout", "30"])

    assert result.exit_code == 0, result.output
    assert "ssh -p 20032 ubuntu@1.2.3.4" in result.output
    assert create.call_args.kwargs["wait"] is True
    assert create.call_args.kwargs["timeout"] == 30


@mock_command_logging
def test_create_surfaces_server_message(monkeypatch) -> None:
    exc = ApiException(status=412, reason="Failed Precondition")
    exc.body = '{"code": 9, "message": "add an SSH key to your account first (Settings → Keys)"}'
    monkeypatch.setattr("lightning_sdk.cli.vm.create.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.create.VM", SimpleNamespace(create=MagicMock(side_effect=exc)))

    result = CliRunner().invoke(create_vm, ["sim-1", "--machine", "H100"])

    assert result.exit_code != 0
    assert "add an SSH key to your account first" in _plain(result.output)
    assert "lightning ssh generate" in _plain(result.output)


@mock_command_logging
def test_list_renders_table(monkeypatch) -> None:
    api = MagicMock()
    api.list_vms.return_value = [
        V1Instance(id="vm-1", name="sim-1", status="running", instance_type="lit-h100-1", ssh_host="1.2.3.4"),
        V1Instance(id="vm-2", name="sim-2", status="pending", instance_type="lit-h100-8"),
    ]
    monkeypatch.setattr("lightning_sdk.cli.vm.list.iter_teamspaces", lambda teamspace, all_teamspaces: [_teamspace()])
    monkeypatch.setattr("lightning_sdk.cli.vm.list.VMApi", MagicMock(return_value=api))

    monkeypatch.setenv("COLUMNS", "200")
    result = CliRunner().invoke(list_vms, [])

    assert result.exit_code == 0, result.output
    assert "sim-1" in result.output
    assert "running" in result.output
    assert "1.2.3.4" in result.output
    assert "lit-h100-8" in result.output
    api.list_vms.assert_called_once_with("ts-1")


def _patch_lookup(monkeypatch, module: str, vm: V1Instance) -> MagicMock:
    api = MagicMock()
    monkeypatch.setattr(f"lightning_sdk.cli.vm.{module}.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr(f"lightning_sdk.cli.vm.{module}.VMApi", MagicMock(return_value=api))
    monkeypatch.setattr(f"lightning_sdk.cli.vm.{module}.resolve_vm", lambda api, teamspace, name: vm)
    return api


@mock_command_logging
def test_inspect_prints_json(monkeypatch) -> None:
    vm = V1Instance(id="vm-1", name="sim-1", status="running", ssh_command="ssh -p 1 u@h")
    _patch_lookup(monkeypatch, "inspect", vm)

    result = CliRunner().invoke(inspect_vm, ["sim-1"])

    assert result.exit_code == 0, result.output
    assert '"id": "vm-1"' in result.output
    assert '"ssh_command": "ssh -p 1 u@h"' in result.output


def _vm_group() -> click.Group:
    group = click.Group(name="vm")
    register_commands(group)
    return group


@mock_command_logging
def test_delete_prompts_and_aborts(monkeypatch) -> None:
    vm = V1Instance(id="vm-1", name="sim-1")
    api = _patch_lookup(monkeypatch, "delete", vm)

    result = CliRunner().invoke(_vm_group(), ["delete", "sim-1"], input="n\n")

    assert result.exit_code != 0
    api.delete_vm.assert_not_called()


@mock_command_logging
def test_delete_with_yes(monkeypatch) -> None:
    vm = V1Instance(id="vm-1", name="sim-1")
    api = _patch_lookup(monkeypatch, "delete", vm)

    result = CliRunner().invoke(_vm_group(), ["delete", "sim-1", "--yes"])

    assert result.exit_code == 0, result.output
    assert "VM deleted" in result.output
    api.delete_vm.assert_called_once_with("vm-1", "org-1")


@mock_command_logging
def test_ssh_execs_command_with_extra_args(monkeypatch) -> None:
    vm = V1Instance(id="vm-1", name="sim-1", status="running", ssh_command="ssh -p 20032 ubuntu@1.2.3.4")
    api = _patch_lookup(monkeypatch, "ssh", vm)
    execvp = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.vm.ssh.os.execvp", execvp)

    result = CliRunner().invoke(ssh_vm, ["sim-1", "--", "-L", "8888:localhost:8888"])

    assert result.exit_code == 0, result.output
    execvp.assert_called_once_with("ssh", ["ssh", "-p", "20032", "ubuntu@1.2.3.4", "-L", "8888:localhost:8888"])
    api.wait_for_status.assert_not_called()


@mock_command_logging
def test_ssh_waits_when_not_running(monkeypatch) -> None:
    pending = V1Instance(id="vm-1", name="sim-1", status="provisioning")
    api = _patch_lookup(monkeypatch, "ssh", pending)
    api.wait_for_status.return_value = V1Instance(
        id="vm-1", name="sim-1", status="running", ssh_command="ssh -p 20032 ubuntu@1.2.3.4"
    )
    execvp = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.vm.ssh.os.execvp", execvp)

    result = CliRunner().invoke(ssh_vm, ["sim-1", "--timeout", "30"])

    assert result.exit_code == 0, result.output
    api.wait_for_status.assert_called_once_with("vm-1", "org-1", timeout=30)
    execvp.assert_called_once()


@mock_command_logging
def test_create_rejects_out_of_range_volume_size(monkeypatch) -> None:
    create = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.vm.create.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.create.VM", SimpleNamespace(create=create))

    result = CliRunner().invoke(create_vm, ["sim-1", "--machine", "H100", "--volume-size", "100"])

    assert result.exit_code != 0
    assert "400" in result.output
    create.assert_not_called()


@mock_command_logging
def test_create_timeout_mentions_cleanup(monkeypatch) -> None:
    timeout = TimeoutError("VM vm-1 did not reach status 'running' within 30s (last: 'pending')")
    monkeypatch.setattr("lightning_sdk.cli.vm.create.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.create.VM", SimpleNamespace(create=MagicMock(side_effect=timeout)))

    result = CliRunner().invoke(create_vm, ["sim-1", "--machine", "H100", "--wait"])

    assert result.exit_code != 0
    assert "did not reach status" in _flat(result.output)
    assert "lightning vm delete" in _flat(result.output)


@mock_command_logging
def test_list_rejects_user_owned_teamspace(monkeypatch) -> None:
    owner = MagicMock(spec=User)
    owner.name = "alice"
    user_teamspace = SimpleNamespace(id="ts-2", name="personal", owner=owner)
    monkeypatch.setattr("lightning_sdk.cli.vm.list.iter_teamspaces", lambda teamspace, all_teamspaces: [user_teamspace])
    monkeypatch.setattr("lightning_sdk.cli.vm.list.VMApi", MagicMock())

    result = CliRunner().invoke(list_vms, [])

    assert result.exit_code != 0
    assert "owned by a user" in _flat(result.output)


@mock_command_logging
def test_inspect_reports_not_found(monkeypatch) -> None:
    api = MagicMock()
    api.get_vm_by_name.return_value = None
    api.get_vm.return_value = None
    monkeypatch.setattr("lightning_sdk.cli.vm.inspect.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.inspect.VMApi", MagicMock(return_value=api))

    result = CliRunner().invoke(inspect_vm, ["ghost"])

    assert result.exit_code != 0
    assert "was not found in teamspace 'ecorp/research'" in _flat(result.output)


@mock_command_logging
def test_inspect_surfaces_server_error_on_lookup(monkeypatch) -> None:
    api = MagicMock()
    api.get_vm_by_name.return_value = None
    api.get_vm.side_effect = ApiException(status=500, reason="Internal Server Error")
    monkeypatch.setattr("lightning_sdk.cli.vm.inspect.resolve_teamspace", lambda teamspace: _teamspace())
    monkeypatch.setattr("lightning_sdk.cli.vm.inspect.VMApi", MagicMock(return_value=api))

    result = CliRunner().invoke(inspect_vm, ["vm-1"])

    assert result.exit_code != 0
    assert "Internal Server Error" in _flat(result.output)
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, ApiException)
