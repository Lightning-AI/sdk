from __future__ import annotations

from unittest import mock

import pytest

from lightning_sdk.api import sandbox_api as sandbox_api_mod
from lightning_sdk.api.sandbox_api import CommandLog, CommandResult, CommandStatus, SandboxApi
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


@pytest.fixture()
def patched_sandbox_api():
    """A :class:`SandboxApi` with ``sandboxes()`` returning a configurable mock service."""
    api = SandboxApi({"api_key": "unit-test-key", "base_url": "https://api.unit.test"})
    mock_svc = mock.MagicMock()
    with mock.patch.object(api, "sandboxes", return_value=mock_svc):
        yield api, mock_svc


def test_parse_run_command_response_none():
    r = sandbox_api_mod._parse_run_command_response(None)
    assert r == CommandResult(cmd_id="", output="", exit_code=0)


def test_parse_run_command_response_with_to_dict():
    resp = mock.MagicMock()
    resp.to_dict.return_value = {"cmd_id": "c1", "output": "out\n", "exit_code": 2}
    r = sandbox_api_mod._parse_run_command_response(resp)
    assert r == CommandResult(cmd_id="c1", output="out\n", exit_code=2)


def test_parse_get_command_response_none():
    s = sandbox_api_mod._parse_get_command_response(None)
    assert s == CommandStatus(output="", exit_code=0, running=False)


def test_parse_get_command_response_running_true():
    resp = mock.MagicMock()
    resp.to_dict.return_value = {"output": "tail", "exit_code": 0, "running": True}
    s = sandbox_api_mod._parse_get_command_response(resp)
    assert s == CommandStatus(output="tail", exit_code=0, running=True)


def test_parse_command_logs_response_empty():
    assert sandbox_api_mod._parse_command_logs_response(None) == []
    assert sandbox_api_mod._parse_command_logs_response(mock.MagicMock(logs=None)) == []


def test_parse_command_logs_response_entries():
    e1 = mock.MagicMock(timestamp="t1", message="m1")
    e2 = mock.MagicMock(timestamp="t2", message="m2")
    resp = mock.MagicMock(logs=[e1, e2])
    logs = sandbox_api_mod._parse_command_logs_response(resp)
    assert logs == [
        CommandLog(timestamp="t1", message="m1"),
        CommandLog(timestamp="t2", message="m2"),
    ]


def test_api_exception_text_prefers_decoded_body():
    exc = ApiException(status=400)
    exc.body = b'{"detail":"bad"}'
    assert "bad" in sandbox_api_mod._api_exception_text(exc)


def test_run_command_returns_command_result(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    resp = mock.MagicMock()
    resp.to_dict.return_value = {"cmd_id": "cmd-9", "output": "hello", "exit_code": 0}
    mock_svc.sandboxes_service_run_sandbox_command.return_value = resp

    result = api.run_command(
        "sandbox-1",
        command="echo",
        args=["a", "b"],
        cwd="/tmp",
        env={"X": "y"},
        detached=True,
    )

    assert isinstance(result, CommandResult)
    assert result.cmd_id == "cmd-9"
    assert result.output == "hello"
    assert result.exit_code == 0

    mock_svc.sandboxes_service_run_sandbox_command.assert_called_once()
    body, sid = mock_svc.sandboxes_service_run_sandbox_command.call_args[0]
    assert sid == "sandbox-1"
    assert body.command == "echo"
    assert body.args == ["a", "b"]
    assert body.cwd == "/tmp"
    assert body.env == {"X": "y"}
    assert body.detached is True


def test_run_command_maps_api_exception_to_runtime_error(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    mock_svc.sandboxes_service_run_sandbox_command.side_effect = ApiException(status=503, reason="unavailable")

    with pytest.raises(RuntimeError, match="Lightning API error 503"):
        api.run_command("sb", command="true")


def test_get_command_returns_command_status(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    resp = mock.MagicMock()
    resp.to_dict.return_value = {"output": "partial", "exit_code": 1, "running": True}
    mock_svc.sandboxes_service_get_sandbox_command.return_value = resp

    status = api.get_command("sandbox-1", "cmd-1", organization_id="org-1")

    assert isinstance(status, CommandStatus)
    assert status.output == "partial"
    assert status.exit_code == 1
    assert status.running is True
    mock_svc.sandboxes_service_get_sandbox_command.assert_called_once_with(
        "sandbox-1", "cmd-1", organization_id="org-1"
    )


def test_get_command_logs_no_org_kwarg_when_missing(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    mock_svc.sandboxes_service_get_sandbox_command_logs.return_value = mock.MagicMock(logs=[])

    api.get_command_logs("sandbox-1", "cmd-1", organization_id=None)

    mock_svc.sandboxes_service_get_sandbox_command_logs.assert_called_once_with("sandbox-1", "cmd-1")


def test_kill_command_passes_organization_id(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api

    api.kill_command("sandbox-1", "cmd-1", organization_id="org-x")

    mock_svc.sandboxes_service_kill_sandbox_command.assert_called_once_with(
        "sandbox-1", "cmd-1", organization_id="org-x"
    )


def test_create_directory_builds_body_and_calls_api(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api

    api.create_directory("sandbox-1", "/tmp/d", organization_id="org-1")

    mock_svc.sandboxes_service_create_sandbox_directory.assert_called_once()
    body, sid = mock_svc.sandboxes_service_create_sandbox_directory.call_args[0]
    assert sid == "sandbox-1"
    assert body.path == "/tmp/d"
    assert body.organization_id == "org-1"


def test_reset_recreates_client(patched_sandbox_api):
    api, _mock_svc = patched_sandbox_api
    client_before = api.client

    api.reset()

    assert api.client is not client_before


def test_get_sandbox_passes_organization_id_from_config(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    api._config["organization_id"] = "org-1"
    mock_svc.sandboxes_service_get_sandbox.return_value = mock.MagicMock()

    api.get_sandbox("sb-1")

    mock_svc.sandboxes_service_get_sandbox.assert_called_once_with("sb-1", organization_id="org-1")


def test_get_sandbox_prefers_explicit_organization_id(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    api._config["organization_id"] = "org-config"
    mock_svc.sandboxes_service_get_sandbox.return_value = mock.MagicMock()

    api.get_sandbox("sb-1", organization_id="org-explicit")

    mock_svc.sandboxes_service_get_sandbox.assert_called_once_with("sb-1", organization_id="org-explicit")


def test_list_sandboxes_forwards_pagination(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    api._config["organization_id"] = "org-1"
    mock_svc.sandboxes_service_list_sandboxes.return_value = mock.MagicMock()

    api.list_sandboxes(page_token="pt", limit=5)

    mock_svc.sandboxes_service_list_sandboxes.assert_called_once_with(
        organization_id="org-1",
        page_token="pt",
        limit=5,
    )


def test_list_snapshots_forwards_filters(patched_sandbox_api):
    from lightning_sdk.lightning_cloud.openapi import V1ListSandboxSnapshotsResponse

    api, mock_svc = patched_sandbox_api
    api._config["organization_id"] = "org-1"
    mock_svc.sandboxes_service_list_sandbox_snapshots.return_value = V1ListSandboxSnapshotsResponse(snapshots=[])

    api.list_snapshots(project_id="proj-1", name="golden", limit=3)

    mock_svc.sandboxes_service_list_sandbox_snapshots.assert_called_once_with(
        organization_id="org-1",
        project_id="proj-1",
        name="golden",
        limit="3",
    )


def test_get_snapshot_and_delete_snapshot_use_org_scope(patched_sandbox_api):
    api, mock_svc = patched_sandbox_api
    api._config["organization_id"] = "org-1"
    mock_svc.sandboxes_service_get_sandbox_snapshot.return_value = mock.MagicMock()

    api.get_snapshot("snap-1")
    api.delete_snapshot("snap-2")

    mock_svc.sandboxes_service_get_sandbox_snapshot.assert_called_once_with(
        "snap-1",
        organization_id="org-1",
    )
    mock_svc.sandboxes_service_delete_sandbox_snapshot.assert_called_once_with(
        "snap-2",
        organization_id="org-1",
    )
