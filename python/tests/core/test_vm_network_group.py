from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lightning_sdk.api.vm_network_group_api import VMNetworkGroupConflictError
from lightning_sdk.lightning_cloud.openapi import V1Instance, V1VMNetworkGroup, V1VMNetworkGroupMember
from lightning_sdk.organization import Organization
from lightning_sdk.vm import VM
from lightning_sdk.vm_network_group import VMNetworkGroup


def _group(revision="3", **kwargs):
    values = {
        "id": "group",
        "name": "nodes",
        "organization_id": "org",
        "project_id": "project",
        "revision": revision,
        "status": "ready",
        "members": [],
    }
    values.update(kwargs)
    return V1VMNetworkGroup(**values)


def _fixture(monkeypatch):
    org = MagicMock(spec=Organization)
    org.id = "org"
    teamspace = SimpleNamespace(id="project", name="research", owner=org)
    api = MagicMock()
    api.get.return_value = _group()
    monkeypatch.setattr("lightning_sdk.vm_network_group._resolve", lambda *_: teamspace)
    monkeypatch.setattr("lightning_sdk.vm_network_group.VMNetworkGroupApi", lambda: api)
    return VMNetworkGroup("group"), api, teamspace


def test_create_and_list_keep_explicit_teamspace_without_cluster_selection(monkeypatch):
    _, api, _ = _fixture(monkeypatch)
    api.create.return_value = _group()
    group = VMNetworkGroup.create("nodes", teamspace="org/research")
    api.create.assert_called_once_with("nodes", "org", "project")
    assert group.name == "nodes"
    api.list.return_value = [_group()]
    assert [group.id for group in VMNetworkGroup.list()] == ["group"]
    api.list.assert_called_once_with("org", "project")


def test_other_teamspace_response_is_rejected(monkeypatch):
    _, api, _ = _fixture(monkeypatch)
    api.get.return_value = _group(project_id="elsewhere")
    with pytest.raises(ValueError, match="selected teamspace"):
        VMNetworkGroup("group")


def test_attach_vm_and_detach_use_snapshot_revision_and_wait_for_ack(monkeypatch):
    group, api, teamspace = _fixture(monkeypatch)
    vm = VM._from_instance(V1Instance(id="vm"), teamspace, "org", MagicMock())
    pending = _group(revision="4", status="pending", members=[V1VMNetworkGroupMember(instance_id="vm")])
    ready = _group(revision="4", members=[V1VMNetworkGroupMember(instance_id="vm", private_address="10.15.1.2")])
    api.set_members.return_value = pending
    api.wait.return_value = ready
    assert group.attach(vm, wait=True, timeout=12) is group
    api.set_members.assert_called_once_with("group", "org", 3, ["vm"])
    api.wait.assert_called_once_with("group", "org", 4, timeout=12)
    assert group.private_addresses == {"vm": "10.15.1.2"}
    api.set_members.return_value = _group(revision="5", status="pending")
    group.detach("vm")
    assert api.set_members.call_args.args == ("group", "org", 4, [])
    assert group.revision == 5


def test_stale_mutation_does_not_refresh_and_overwrite_new_members(monkeypatch):
    group, api, _ = _fixture(monkeypatch)
    api.set_members.side_effect = VMNetworkGroupConflictError("changed")
    api.get.reset_mock()
    with pytest.raises(VMNetworkGroupConflictError):
        group.attach("vm")
    api.get.assert_not_called()
    assert group.revision == 3


def test_reject_foreign_vm_and_duplicate_members_before_mutation(monkeypatch):
    group, api, _ = _fixture(monkeypatch)
    vm = VM._from_instance(V1Instance(id="vm"), SimpleNamespace(id="other", name="other"), "org", MagicMock())
    with pytest.raises(ValueError, match="teamspace"):
        group.attach(vm)
    with pytest.raises(ValueError, match="Duplicate"):
        group.set_members(["vm", "vm"])
    api.set_members.assert_not_called()


def test_delete_wait_is_available_without_an_addition_check(monkeypatch):
    group, api, _ = _fixture(monkeypatch)
    group.delete(wait=True, timeout=9)
    api.delete.assert_called_once_with("group", "org")
    api.wait.assert_called_once_with("group", "org", 3, timeout=9, deleted=True)
