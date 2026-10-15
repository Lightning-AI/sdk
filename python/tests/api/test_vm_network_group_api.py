import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import MagicMock

import pytest

from lightning_sdk.api.vm_network_group_api import VMNetworkGroupApi, VMNetworkGroupConflictError
from lightning_sdk.lightning_cloud.openapi import (
    ApiClient,
    CloudInstancesServiceApi,
    Configuration,
    V1VMNetworkGroup,
    V1VMNetworkGroupMember,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


def _api(monkeypatch):
    constructor = MagicMock()
    monkeypatch.setattr("lightning_sdk.api.vm_network_group_api.LightningClient", constructor)
    api = VMNetworkGroupApi()
    constructor.assert_called_once_with(retry=False)
    return api


def test_mutation_conflict_is_not_retried(monkeypatch):
    api = _api(monkeypatch)
    rpc = api._client.cloud_instances_service_set_vm_network_group_members
    rpc.side_effect = ApiException(status=409)
    with pytest.raises(VMNetworkGroupConflictError, match="refresh"):
        api.set_members("group", "org", 3, ["vm"])
    rpc.assert_called_once()
    body = rpc.call_args.kwargs["body"]
    assert body.expected_revision == "3"
    assert body.instance_ids == ["vm"]


def test_missing_group_and_cleanup_remain_distinct_from_other_failures(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_vm_network_group.side_effect = ApiException(status=404)
    assert api.get("group", "org") is None
    api._client.cloud_instances_service_delete_vm_network_group.side_effect = ApiException(status=404)
    api.delete("group", "org")
    api._client.cloud_instances_service_get_vm_network_group.side_effect = ApiException(status=403)
    with pytest.raises(ApiException):
        api.get("group", "org")
    api._client.cloud_instances_service_delete_vm_network_group.side_effect = ApiException(status=403)
    with pytest.raises(ApiException):
        api.delete("group", "org")


def test_wait_requires_acknowledgement_and_addresses(monkeypatch):
    api = _api(monkeypatch)
    rpc = api._client.cloud_instances_service_get_vm_network_group
    ready = V1VMNetworkGroup(
        revision="3", status="ready", members=[V1VMNetworkGroupMember(private_address="10.15.1.2")]
    )
    rpc.side_effect = [
        V1VMNetworkGroup(revision="3", status="pending"),
        V1VMNetworkGroup(revision="3", status="ready", members=[V1VMNetworkGroupMember(instance_id="vm")]),
        ready,
    ]
    sleep = MagicMock()
    assert api.wait("group", "org", 3, sleep=sleep, clock=lambda: 0) is ready
    assert sleep.call_count == 2
    assert all(call.args == (1,) for call in sleep.call_args_list)
    assert rpc.call_args.kwargs["_request_timeout"] == 600


def test_wait_does_not_hide_concurrent_membership_changes(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_vm_network_group.return_value = V1VMNetworkGroup(
        revision="4", status="ready"
    )
    with pytest.raises(VMNetworkGroupConflictError):
        api.wait("group", "org", 3)


def test_wait_timeout_preserves_last_host_error_without_real_sleep(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_vm_network_group.return_value = V1VMNetworkGroup(
        revision="3", status="pending", error="host unavailable"
    )
    times = iter([0, 0, 5])
    with pytest.raises(TimeoutError, match="host unavailable"):
        api.wait("group", "org", 3, timeout=5, clock=lambda: next(times), sleep=MagicMock())


def test_delete_waits_until_the_group_disappears(monkeypatch):
    api = _api(monkeypatch)
    api._client.cloud_instances_service_get_vm_network_group.side_effect = [
        V1VMNetworkGroup(status="deleting", revision="4"),
        ApiException(status=404),
    ]
    assert api.wait("group", "org", 3, deleted=True, sleep=MagicMock(), clock=lambda: 0) is None


def test_generated_client_round_trips_the_network_group_wire_contract(monkeypatch):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def _handle(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length)) if length else None
            calls.append((self.command, self.path, body))
            group = {
                "id": "group",
                "organizationId": "org",
                "projectId": "project",
                "clusterId": "cluster",
                "revision": "9007199254740993",
                "status": "ready",
                "members": [{"instanceId": "vm", "privateAddress": "10.15.1.2"}],
            }
            response = {"networkGroups": [group]} if self.path.startswith("/v1/core/vm-network-groups?") else group
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        do_POST = do_GET = do_PUT = do_DELETE = _handle  # noqa: N815

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    # The suite patches threading.Thread; this class was captured before the fixture runs.
    thread = Thread(target=server.serve_forever)
    thread.start()
    config = Configuration()
    config.host = f"http://127.0.0.1:{server.server_port}"
    client = ApiClient(config)
    monkeypatch.setattr(
        "lightning_sdk.api.vm_network_group_api.LightningClient", lambda **_: CloudInstancesServiceApi(client)
    )
    try:
        api = VMNetworkGroupApi()
        assert api.create("nodes", "org", "project", "cluster").id == "group"
        assert api.get("group", "org").members[0].private_address == "10.15.1.2"
        assert len(api.list("org", "project")) == 1
        revision = 9007199254740993
        assert int(api.set_members("group", "org", revision, ["vm"]).revision) == revision
        api.delete("group", "org")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        client.rest_client.pool_manager.clear()
    assert calls[0][2] == {"name": "nodes", "organizationId": "org", "projectId": "project", "clusterId": "cluster"}
    assert calls[1][1] == "/v1/core/vm-network-groups/group?organizationId=org"
    assert "organizationId=org" in calls[2][1]
    assert "projectId=project" in calls[2][1]
    assert calls[3] == (
        "PUT",
        "/v1/core/vm-network-groups/group/members",
        {"organizationId": "org", "expectedRevision": str(revision), "instanceIds": ["vm"]},
    )
    assert calls[4][1] == "/v1/core/vm-network-groups/group?organizationId=org"
