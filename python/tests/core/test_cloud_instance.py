from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from lightning_sdk.cloud_instance import CloudInstance, InstanceImage, InstanceType
from lightning_sdk.lightning_cloud.openapi import V1Instance


@pytest.fixture()
def instance_api():
    """Patch out the internal API and org resolution used by :class:`CloudInstance`."""
    with (
        mock.patch("lightning_sdk.cloud_instance.InstanceApi") as api_cls,
        mock.patch("lightning_sdk.cloud_instance._resolve_org_id", return_value="org-1"),
    ):
        yield api_cls.return_value


def _instance(**kwargs) -> V1Instance:
    defaults = {
        "id": "i-1",
        "name": "vm",
        "organization_id": "org-1",
        "cluster_id": "lightning-baremetal",
        "instance_type": "cpu-4",
        "volume_size": "400",
        "status": "running",
        "ports": ["8080"],
        "ssh_user": "ubuntu",
        "ssh_host": "203.0.113.10",
        "ssh_port": 2201,
        "ssh_command": "ssh -p 2201 ubuntu@203.0.113.10",
    }
    defaults.update(kwargs)
    return V1Instance(**defaults)


def test_create_passes_arguments_through(instance_api):
    instance_api.list_instance_cloud_accounts.return_value = ["lightning-baremetal"]
    instance_api.create_instance.return_value = _instance()

    instance = CloudInstance.create(
        name="vm",
        instance_type="cpu-4",
        ports=["8080", 9090],
        volume_size=400,
        cloud_init="#cloud-config\n",
    )

    assert instance.id == "i-1"
    assert instance_api.create_instance.call_args.kwargs == {
        "name": "vm",
        "organization_id": "org-1",
        "cloud_account": "lightning-baremetal",
        "instance_type": "cpu-4",
        "volume_size": 400,
        "spot": False,
        "ports": [8080, 9090],
        "image": None,
        "cloud_init": "#cloud-config\n",
    }


def test_create_requires_an_unambiguous_cloud_account(instance_api):
    instance_api.list_instance_cloud_accounts.return_value = ["a", "b"]

    with pytest.raises(ValueError, match="Specify one of: a, b"):
        CloudInstance.create(name="vm", instance_type="cpu-4")


def test_create_waits_for_a_connectable_instance(instance_api):
    instance_api.list_instance_cloud_accounts.return_value = ["lightning-baremetal"]
    instance_api.create_instance.return_value = _instance(status="pending", ssh_command="")
    polled = [
        _instance(status="provisioning", ssh_command=""),
        # running but without an SSH endpoint yet: not connectable, so keep waiting
        _instance(status="running", ssh_command=""),
    ]
    instance_api.get_instance.side_effect = lambda **_: polled.pop(0) if polled else _instance()

    with mock.patch("lightning_sdk.cloud_instance.time.sleep") as sleep:
        instance = CloudInstance.create(name="vm", instance_type="cpu-4", wait=True, timeout=10)

    assert instance_api.get_instance.call_count == 3
    assert sleep.call_count == 2
    assert instance.ssh_command == "ssh -p 2201 ubuntu@203.0.113.10"


def test_wait_until_running_raises_on_failure(instance_api):
    instance_api.get_instance.return_value = _instance(status="failed", status_reason="out of capacity")
    instance = CloudInstance("i-1")

    with pytest.raises(RuntimeError, match="is failed: out of capacity"):
        instance.wait_until_running(timeout=10)


def test_wait_until_running_times_out(instance_api):
    instance_api.get_instance.return_value = _instance(status="pending", ssh_command="")
    instance = CloudInstance("i-1")

    with pytest.raises(TimeoutError, match="still pending after 0 seconds"):
        instance.wait_until_running(timeout=0)


def test_lookup_by_id(instance_api):
    instance_api.get_instance.return_value = _instance()

    instance = CloudInstance("i-1")

    assert instance.name == "vm"
    assert instance_api.get_instance.call_args.kwargs == {"instance_id": "i-1", "organization_id": "org-1"}
    instance_api.list_instances.assert_not_called()


def test_lookup_falls_back_to_name(instance_api):
    instance_api.get_instance.side_effect = RuntimeError("Lightning API error 500: failed to get server: not found")
    instance_api.list_instances.return_value = [_instance(id="i-2", name="other"), _instance()]

    assert CloudInstance("vm").id == "i-1"


def test_lookup_reports_unknown_names(instance_api):
    instance_api.get_instance.side_effect = RuntimeError("failed to get server: not found")
    instance_api.list_instances.return_value = []

    with pytest.raises(ValueError, match="Instance nope does not exist"):
        CloudInstance("nope")


def test_lookup_rejects_ambiguous_names(instance_api):
    instance_api.get_instance.side_effect = RuntimeError("failed to get server: not found")
    instance_api.list_instances.return_value = [_instance(id="i-1"), _instance(id="i-2")]

    with pytest.raises(ValueError, match="Specify one by ID: i-1, i-2"):
        CloudInstance("vm")


def test_lookup_does_not_hide_unrelated_errors(instance_api):
    instance_api.get_instance.side_effect = PermissionError("Not allowed to manage instances")

    with pytest.raises(PermissionError):
        CloudInstance("i-1")
    instance_api.list_instances.assert_not_called()


def test_list_reuses_the_listed_state(instance_api):
    instance_api.list_instances.return_value = [_instance(id="i-1"), _instance(id="i-2")]

    instances = CloudInstance.list()

    assert [i.id for i in instances] == ["i-1", "i-2"]
    # listing already returned full rows, so no per-instance fetch should happen
    instance_api.get_instance.assert_not_called()


def test_images_puts_the_default_first(instance_api):
    instance_api.list_instance_images.return_value = (
        [
            SimpleNamespace(name="a-image", description="A"),
            SimpleNamespace(name="z-image", description="Z"),
        ],
        "z-image",
    )

    assert CloudInstance.images() == [
        InstanceImage(name="z-image", description="Z"),
        InstanceImage(name="a-image", description="A"),
    ]


def test_instance_types(instance_api):
    instance_api.list_instance_cloud_accounts.return_value = ["lightning-baremetal"]
    instance_api.list_instance_types.return_value = [("cpu-4", "4 CPU, 16 GB RAM", 0.33)]

    assert CloudInstance.instance_types() == [InstanceType(name="cpu-4", description="4 CPU, 16 GB RAM", cost=0.33)]


def test_ssh_args_uses_the_reported_endpoint(instance_api):
    instance_api.get_instance.return_value = _instance()
    instance = CloudInstance("i-1")

    args = instance.ssh_args(command=["uname", "-a"], options=["StrictHostKeyChecking=no"], key_path="/tmp/key")

    assert args == [
        "ssh",
        "-i",
        "/tmp/key",
        "-p",
        "2201",
        "-o",
        "StrictHostKeyChecking=no",
        "ubuntu@203.0.113.10",
        "uname",
        "-a",
    ]


def test_ssh_runs_the_built_command(instance_api):
    instance_api.get_instance.return_value = _instance()
    instance = CloudInstance("i-1")

    with mock.patch("lightning_sdk.cloud_instance.subprocess.run", return_value=SimpleNamespace(returncode=7)) as run:
        assert instance.ssh("uname -a", key_path="/tmp/key") == 7

    assert run.call_args.args[0] == [
        "ssh",
        "-i",
        "/tmp/key",
        "-p",
        "2201",
        "ubuntu@203.0.113.10",
        "uname -a",
    ]


def test_ssh_args_rejects_instances_without_an_endpoint(instance_api):
    instance_api.get_instance.return_value = _instance(status="pending", ssh_host="", ssh_port=0, ssh_command="")
    instance = CloudInstance("i-1")

    with pytest.raises(RuntimeError, match="is pending and has no SSH endpoint yet"):
        instance.ssh_args(key_path="/tmp/key")


def test_delete(instance_api):
    instance_api.get_instance.return_value = _instance()

    CloudInstance("i-1").delete()

    assert instance_api.delete_instance.call_args.kwargs == {"instance_id": "i-1", "organization_id": "org-1"}


def test_to_dict_normalizes_wire_types(instance_api):
    instance_api.get_instance.return_value = _instance()

    data = CloudInstance("i-1").to_dict()

    assert data["volume_size"] == 400
    assert data["ports"] == [8080]
    assert data["cloud_account"] == "lightning-baremetal"


def test_unbound_instance_has_no_state(instance_api):
    instance = CloudInstance()

    with pytest.raises(RuntimeError, match="No instance is bound"):
        _ = instance.id
    assert repr(instance) == "CloudInstance(unbound)"
