from unittest.mock import MagicMock

import pytest

from lightning_sdk.api.vm_api import VMApi, VMFailedError, VMNotFoundError
from lightning_sdk.lightning_cloud.openapi import V1Instance, V1ListInstancesResponse
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


def _api(monkeypatch) -> VMApi:
    monkeypatch.setattr("lightning_sdk.api.vm_api.LightningClient", MagicMock())
    return VMApi()


def _not_found() -> ApiException:
    return ApiException(status=404, reason="Not Found")


def test_create_vm_builds_request(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_create_instance.return_value = V1Instance(id="vm-1")

    result = api.create_vm(
        name="sim-1",
        org_id="org-1",
        teamspace_id="ts-1",
        cluster_id="cl-1",
        instance_type="lit-h100-1",
        volume_size=500,
        spot=True,
    )

    assert result.id == "vm-1"
    body = api._client.cloud_instances_service_create_instance.call_args.kwargs["body"]
    assert body.name == "sim-1"
    assert body.organization_id == "org-1"
    assert body.project_id == "ts-1"
    assert body.cluster_id == "cl-1"
    assert body.instance_type == "lit-h100-1"
    assert body.volume_size == "500"
    assert body.spot is True


def test_create_vm_omits_volume_size_when_unset(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_create_instance.return_value = V1Instance(id="vm-1")

    api.create_vm(name="n", org_id="o", teamspace_id="t", cluster_id="c", instance_type="i")

    body = api._client.cloud_instances_service_create_instance.call_args.kwargs["body"]
    assert body.volume_size is None


def test_get_vm_returns_none_on_404(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_instance.side_effect = _not_found()

    assert api.get_vm("vm-1", "org-1") is None
    api._client.cloud_instances_service_get_instance.assert_called_once_with(id="vm-1", organization_id="org-1")


def test_get_vm_reraises_other_errors(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_instance.side_effect = ApiException(status=500, reason="boom")

    with pytest.raises(ApiException):
        api.get_vm("vm-1", "org-1")


def test_list_vms_follows_pagination(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_list_instances.side_effect = [
        V1ListInstancesResponse(instances=[V1Instance(id="a")], next_page_token="p2"),
        V1ListInstancesResponse(instances=[V1Instance(id="b")], next_page_token=""),
    ]

    result = api.list_vms("ts-1", "org-1")

    assert [vm.id for vm in result] == ["a", "b"]
    calls = api._client.cloud_instances_service_list_instances.call_args_list
    assert calls[0].kwargs == {"organization_id": "org-1", "project_id": "ts-1", "limit": "100"}
    assert calls[1].kwargs["page_token"] == "p2"


def test_get_vm_by_name_filters_list(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_list_instances.return_value = V1ListInstancesResponse(
        instances=[V1Instance(id="a", name="x"), V1Instance(id="b", name="sim-1")], next_page_token=""
    )

    assert api.get_vm_by_name("sim-1", "ts-1", "org-1").id == "b"
    assert api.get_vm_by_name("nope", "ts-1", "org-1") is None


def test_delete_vm(monkeypatch):
    api = _api(monkeypatch)

    api.delete_vm("vm-1", "org-1")

    api._client.cloud_instances_service_delete_instance.assert_called_once_with(id="vm-1", organization_id="org-1")


def _fake_clock(step: float):
    now = [0.0]

    def clock() -> float:
        now[0] += step
        return now[0]

    return clock


def test_wait_for_status_returns_on_target(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_instance.side_effect = [
        V1Instance(id="vm-1", status="pending"),
        V1Instance(id="vm-1", status="provisioning"),
        V1Instance(id="vm-1", status="running"),
    ]
    sleep = MagicMock()

    result = api.wait_for_status("vm-1", "org-1", timeout=60, poll_interval=1, sleep=sleep, clock=_fake_clock(1))

    assert result.status == "running"
    assert sleep.call_count == 2


def test_wait_for_status_raises_on_failure(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_instance.return_value = V1Instance(
        id="vm-1", status="failed", status_reason="no capacity"
    )

    with pytest.raises(VMFailedError, match="no capacity"):
        api.wait_for_status("vm-1", "org-1", timeout=60, sleep=MagicMock(), clock=_fake_clock(1))


def test_wait_for_status_raises_when_vm_disappears(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_instance.side_effect = _not_found()

    with pytest.raises(VMNotFoundError):
        api.wait_for_status("vm-1", "org-1", timeout=60, sleep=MagicMock(), clock=_fake_clock(1))


def test_wait_for_status_times_out(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_instance.return_value = V1Instance(id="vm-1", status="pending")

    with pytest.raises(TimeoutError):
        api.wait_for_status("vm-1", "org-1", timeout=5, poll_interval=1, sleep=MagicMock(), clock=_fake_clock(2))
