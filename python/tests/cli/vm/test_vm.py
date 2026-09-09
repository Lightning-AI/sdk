from types import SimpleNamespace
from unittest.mock import MagicMock

from click.testing import CliRunner

from lightning_sdk.cli.vm.create import create_vm
from lightning_sdk.cli.vm.list import list_vms
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from tests.cli.help import assert_help_contains, mock_command_logging


def _teamspace() -> SimpleNamespace:
    return SimpleNamespace(id="ts-1", name="research", owner=SimpleNamespace(id="org-1", name="ecorp"))


@mock_command_logging
def test_vm_help() -> None:
    assert_help_contains(
        "lightning vm --help",
        "Usage: lightning vm [OPTIONS] COMMAND [ARGS]...",
        "Create and manage virtual machines.",
        "create",
        "list",
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
    assert "add an SSH key to your account first" in result.output
    assert "lightning ssh generate" in result.output


@mock_command_logging
def test_list_renders_table(monkeypatch) -> None:
    api = MagicMock()
    api.list_vms.return_value = [
        V1Instance(id="vm-1", name="sim-1", status="running", instance_type="lit-h100-1", ssh_host="1.2.3.4"),
        V1Instance(id="vm-2", name="sim-2", status="pending", instance_type="lit-h100-8"),
    ]
    monkeypatch.setattr("lightning_sdk.cli.vm.list.iter_teamspaces", lambda teamspace, all_teamspaces: [_teamspace()])
    monkeypatch.setattr("lightning_sdk.cli.vm.list.VMApi", MagicMock(return_value=api))

    result = CliRunner().invoke(list_vms, [])

    assert result.exit_code == 0, result.output
    assert "sim-1" in result.output
    assert "running" in result.output
    assert "1.2.3.4" in result.output
    assert "lit-h100-8" in result.output
    api.list_vms.assert_called_once_with("ts-1", "org-1")
