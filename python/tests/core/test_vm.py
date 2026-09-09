from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lightning_sdk.api.utils import _machine_to_compute_name
from lightning_sdk.lightning_cloud.openapi import V1Instance
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.user import User
from lightning_sdk.vm import VM, _require_org_id


def _org_teamspace() -> SimpleNamespace:
    org = MagicMock(spec=Organization)
    org.id = "org-1"
    org.name = "ecorp"
    return SimpleNamespace(id="ts-1", name="research", owner=org)


def _user_teamspace() -> SimpleNamespace:
    user = MagicMock(spec=User)
    user.name = "alice"
    return SimpleNamespace(id="ts-2", name="personal", owner=user)


def _patch_resolution(monkeypatch, teamspace, api: MagicMock) -> None:
    monkeypatch.setattr(
        "lightning_sdk.vm._resolve_teamspace",
        lambda teamspace=None, org=None, user=None, _resolved=teamspace: _resolved,
    )
    monkeypatch.setattr("lightning_sdk.vm.VMApi", MagicMock(return_value=api))


def test_require_org_id_rejects_user_owned_teamspace():
    with pytest.raises(ValueError, match="organization"):
        _require_org_id(_user_teamspace())


def test_require_org_id_returns_org_id():
    assert _require_org_id(_org_teamspace()) == "org-1"


def test_init_loads_by_name(monkeypatch):
    api = MagicMock()
    api.get_vm_by_name.return_value = V1Instance(id="vm-1", name="sim-1", status="running")
    _patch_resolution(monkeypatch, _org_teamspace(), api)

    vm = VM("sim-1", teamspace="ecorp/research")

    assert vm.id == "vm-1"
    assert vm.status == "running"
    api.get_vm_by_name.assert_called_once_with("sim-1", "ts-1", "org-1")


def test_init_falls_back_to_id(monkeypatch):
    api = MagicMock()
    api.get_vm_by_name.return_value = None
    api.get_vm.return_value = V1Instance(id="vm-1", name="sim-1")
    _patch_resolution(monkeypatch, _org_teamspace(), api)

    vm = VM("vm-1")

    assert vm.name == "sim-1"
    api.get_vm.assert_called_once_with("vm-1", "org-1")


def test_init_raises_when_missing(monkeypatch):
    api = MagicMock()
    api.get_vm_by_name.return_value = None
    api.get_vm.return_value = None
    _patch_resolution(monkeypatch, _org_teamspace(), api)

    with pytest.raises(ValueError, match="not found"):
        VM("ghost")


def test_create_resolves_machine_and_cloud_account(monkeypatch):
    api = MagicMock()
    api.create_vm.return_value = V1Instance(id="vm-1", name="sim-1", status="pending")
    _patch_resolution(monkeypatch, _org_teamspace(), api)
    determine = MagicMock(return_value="cl-default")
    monkeypatch.setattr(
        "lightning_sdk.vm.TeamspaceApi", MagicMock(return_value=SimpleNamespace(_determine_cloud_account=determine))
    )

    vm = VM.create("sim-1", machine=Machine.H100, volume_size=500)

    assert vm.id == "vm-1"
    kwargs = api.create_vm.call_args.kwargs
    assert kwargs["name"] == "sim-1"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["teamspace_id"] == "ts-1"
    assert kwargs["cluster_id"] == "cl-default"
    assert kwargs["instance_type"] == _machine_to_compute_name(Machine.H100)
    assert kwargs["volume_size"] == 500
    determine.assert_called_once_with("ts-1")


def test_create_with_explicit_cloud_account_and_wait(monkeypatch):
    api = MagicMock()
    api.create_vm.return_value = V1Instance(id="vm-1", name="sim-1", status="pending")
    api.wait_for_status.return_value = V1Instance(
        id="vm-1", name="sim-1", status="running", ssh_command="ssh -p 20032 ubuntu@1.2.3.4"
    )
    _patch_resolution(monkeypatch, _org_teamspace(), api)

    vm = VM.create("sim-1", machine="H100", cloud_account="cl-explicit", wait=True, timeout=30)

    assert api.create_vm.call_args.kwargs["cluster_id"] == "cl-explicit"
    api.wait_for_status.assert_called_once_with("vm-1", "org-1", timeout=30)
    assert vm.status == "running"
    assert vm.ssh_command == "ssh -p 20032 ubuntu@1.2.3.4"


def test_create_rejects_user_owned_teamspace(monkeypatch):
    api = MagicMock()
    _patch_resolution(monkeypatch, _user_teamspace(), api)

    with pytest.raises(ValueError, match="organization"):
        VM.create("sim-1", machine=Machine.H100)
    api.create_vm.assert_not_called()


def test_list(monkeypatch):
    api = MagicMock()
    api.list_vms.return_value = [V1Instance(id="a", name="x"), V1Instance(id="b", name="y")]
    _patch_resolution(monkeypatch, _org_teamspace(), api)

    vms = VM.list()

    assert [vm.name for vm in vms] == ["x", "y"]
    api.list_vms.assert_called_once_with("ts-1", "org-1")


def test_refresh_wait_delete(monkeypatch):
    api = MagicMock()
    api.get_vm_by_name.return_value = V1Instance(id="vm-1", name="sim-1", status="pending")
    api.get_vm.return_value = V1Instance(id="vm-1", name="sim-1", status="provisioning")
    api.wait_for_status.return_value = V1Instance(id="vm-1", name="sim-1", status="running")
    _patch_resolution(monkeypatch, _org_teamspace(), api)
    vm = VM("sim-1")

    vm.refresh()
    assert vm.status == "provisioning"

    vm.wait(timeout=12)
    assert vm.status == "running"
    api.wait_for_status.assert_called_once_with("vm-1", "org-1", timeout=12)

    vm.delete()
    api.delete_vm.assert_called_once_with("vm-1", "org-1")


def test_properties_map_instance_fields(monkeypatch):
    api = MagicMock()
    api.get_vm_by_name.return_value = V1Instance(
        id="vm-1",
        name="sim-1",
        status="running",
        instance_type="lit-h100-1",
        ssh_command="ssh -p 20032 ubuntu@1.2.3.4",
        ssh_host="1.2.3.4",
        ssh_port=20032,
        ssh_user="ubuntu",
    )
    _patch_resolution(monkeypatch, _org_teamspace(), api)

    vm = VM("sim-1")

    assert vm.machine == "lit-h100-1"
    assert vm.ssh_host == "1.2.3.4"
    assert vm.ssh_port == 20032
    assert vm.ssh_user == "ubuntu"
    assert vm.teamspace.id == "ts-1"
    assert "sim-1" in repr(vm)


def test_vm_is_exported():
    import lightning_sdk

    assert lightning_sdk.VM is VM
