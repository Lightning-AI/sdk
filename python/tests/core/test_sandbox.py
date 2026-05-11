from __future__ import annotations

from unittest import mock

import pytest

from lightning_sdk.api.sandbox_api import CommandResult, CommandStatus, SandboxApi
from lightning_sdk.lightning_cloud.openapi import V1ListSandboxesResponse, V1Sandbox
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.sandbox import Command, RunCommandOpts, Sandbox, SandboxConfig, WriteFileParams
from lightning_sdk.sandbox.base import SandboxInstance, _resolve_sandbox_api, create_sandbox


def _v1(**kwargs) -> V1Sandbox:
    defaults: dict = {
        "id": "sb-default",
        "name": "sb-name",
        "status": "running",
        "organization_id": "org-1",
        "instance_type": "cpu.small",
        "spot": False,
        "ports": [],
        "cluster_id": "",
        "cloudspace_id": "",
    }
    defaults.update(kwargs)
    return V1Sandbox(**defaults)


def test_resolve_sandbox_api_rejects_config_and_api_together():
    cfg = SandboxConfig(api_key="k", base_url="https://x")
    fake_api = mock.MagicMock()
    with pytest.raises(ValueError, match="only one"):
        _resolve_sandbox_api(sandbox_api=fake_api, config=cfg)


def test_create_sandbox_waits_until_running():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test"})
    mock_sb = mock.MagicMock()
    with mock.patch.object(api, "sandboxes", return_value=mock_sb):
        pending = _v1(id="sb-1", name="n", status="pending")
        running = _v1(id="sb-1", name="n", status="running")
        mock_sb.sandboxes_service_create_sandbox.return_value = pending
        mock_sb.sandboxes_service_get_sandbox.return_value = running

        with mock.patch("lightning_sdk.sandbox.base.time.sleep"):
            inst = create_sandbox(name="n", sandbox_api=api)

    assert inst.sandbox_id == "sb-1"
    assert inst.status == "running"
    mock_sb.sandboxes_service_get_sandbox.assert_called_once()


def test_create_sandbox_raises_on_terminal_status():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test"})
    mock_sb = mock.MagicMock()
    with mock.patch.object(api, "sandboxes", return_value=mock_sb):
        err = _v1(id="sb-1", status="error")
        mock_sb.sandboxes_service_create_sandbox.return_value = err

        with pytest.raises(RuntimeError, match="terminal state"):
            create_sandbox(name="n", sandbox_api=api)


def test_sandbox_instance_run_command_string_and_args():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="c1", output="hi", exit_code=0)
    sb = SandboxInstance(_v1(id="sb-1", organization_id="org-1"), sandbox_api=mock_api)

    r = sb.run_command("echo", args=["hello", "world"])

    assert r.output == "hi"
    mock_api.run_command.assert_called_once_with(
        "sb-1", command="echo", args=["hello", "world"], organization_id="org-1"
    )


def test_sandbox_instance_run_command_auto_splits_simple_command():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="", output="", exit_code=0)
    sb = SandboxInstance(_v1(id="sb-2", organization_id=None), sandbox_api=mock_api)

    sb.run_command("uname -a")

    mock_api.run_command.assert_called_once()
    kwargs = mock_api.run_command.call_args.kwargs
    assert kwargs["command"] == "uname"
    assert kwargs["args"] == ["-a"]


def test_sandbox_instance_run_command_run_command_opts():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="d1", output="", exit_code=0)
    sb = SandboxInstance(_v1(id="sb-3", organization_id="o"), sandbox_api=mock_api)

    cmd = sb.run_command(
        RunCommandOpts(
            cmd="sh",
            args=["-c", "echo ok"],
            cwd="/tmp",
            env={"A": "b"},
            detached=True,
        )
    )

    assert isinstance(cmd, Command)
    assert cmd.cmd_id == "d1"
    assert cmd.exit_code is None
    assert cmd.running is True
    mock_api.run_command.assert_called_once_with(
        "sb-3",
        command="sh",
        args=["-c", "echo ok"],
        organization_id="o",
        cwd="/tmp",
        env={"A": "b"},
        sudo=None,
        detached=True,
    )


def test_sandbox_instance_run_command_non_detached_returns_finished_command():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="c1", output="hi", exit_code=0)
    sb = SandboxInstance(_v1(id="sb-nd", organization_id="o"), sandbox_api=mock_api)

    cmd = sb.run_command("echo", args=["hi"])

    assert isinstance(cmd, Command)
    assert cmd.cmd_id == "c1"
    assert cmd.exit_code == 0
    assert cmd.running is False
    assert cmd.output == "hi"


def test_command_wait_polls_until_done_for_detached():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="c-bg", output="", exit_code=0)
    mock_api.get_command.side_effect = [
        CommandStatus(output="", exit_code=0, running=True),
        CommandStatus(output="done\n", exit_code=7, running=False),
    ]
    sb = SandboxInstance(_v1(id="sb-bg", organization_id="o"), sandbox_api=mock_api)

    cmd = sb.run_command(RunCommandOpts(cmd="sleep", args=["5"], detached=True))
    assert cmd.exit_code is None

    with mock.patch("lightning_sdk.sandbox.base.time.sleep"):
        result = cmd.wait(poll_interval=0.0)

    assert result is cmd
    assert cmd.exit_code == 7
    assert cmd.running is False
    assert cmd.output == "done\n"


def test_command_wait_returns_immediately_when_already_finished():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="c1", output="hi", exit_code=0)
    sb = SandboxInstance(_v1(id="sb-done", organization_id="o"), sandbox_api=mock_api)

    cmd = sb.run_command("echo", args=["hi"])
    result = cmd.wait()

    assert result is cmd
    mock_api.get_command.assert_not_called()


def test_command_kill_calls_kill_command():
    mock_api = mock.MagicMock()
    mock_api.run_command.return_value = CommandResult(cmd_id="c-k", output="", exit_code=0)
    sb = SandboxInstance(_v1(id="sb-k", organization_id="org-k"), sandbox_api=mock_api)

    cmd = sb.run_command(RunCommandOpts(cmd="sleep", args=["100"], detached=True))
    cmd.kill()

    mock_api.kill_command.assert_called_once_with("sb-k", "c-k", "org-k")


def test_sandbox_instance_wait_for_command_polls_until_done():
    mock_api = mock.MagicMock()
    mock_api.get_command.side_effect = [
        CommandStatus(output="", exit_code=0, running=True),
        CommandStatus(output="done\n", exit_code=0, running=False),
    ]
    sb = SandboxInstance(_v1(id="sb-w", organization_id="org-w"), sandbox_api=mock_api)

    with mock.patch("lightning_sdk.sandbox.base.time.sleep"):
        final = sb.wait_for_command("c-1", poll_interval=0.0)

    assert final.running is False
    assert final.output == "done\n"
    assert mock_api.get_command.call_count == 2
    mock_api.get_command.assert_called_with("sb-w", "c-1", "org-w")


def test_sandbox_instance_wait_for_command_times_out():
    mock_api = mock.MagicMock()
    mock_api.get_command.return_value = CommandStatus(output="", exit_code=0, running=True)
    sb = SandboxInstance(_v1(id="sb-t"), sandbox_api=mock_api)

    monotonic_values = iter([0.0, 0.0, 10.0])

    with (
        mock.patch("lightning_sdk.sandbox.base.time.sleep"),
        mock.patch("lightning_sdk.sandbox.base.time.monotonic", side_effect=lambda: next(monotonic_values)),
        pytest.raises(TimeoutError, match="Timed out"),
    ):
        sb.wait_for_command("c-1", timeout=1.0, poll_interval=0.0)


def test_sandbox_instance_read_file_returns_none_on_404():
    mock_api = mock.MagicMock()
    sb_svc = mock.MagicMock()
    mock_api.sandboxes.return_value = sb_svc
    sb_svc.sandboxes_service_get_sandbox_file.side_effect = ApiException(status=404)

    sb = SandboxInstance(_v1(id="sb-4", organization_id="org"), sandbox_api=mock_api)

    assert sb.read_file("/missing") is None


def test_sandbox_instance_stop_swallows_404():
    mock_api = mock.MagicMock()
    sb_svc = mock.MagicMock()
    mock_api.sandboxes.return_value = sb_svc
    sb_svc.sandboxes_service_delete_sandbox.side_effect = ApiException(status=404)

    sb = SandboxInstance(_v1(id="sb-5", organization_id="org"), sandbox_api=mock_api)
    sb.stop()


def test_sandbox_instance_list_builds_result():
    mock_api = mock.MagicMock()
    sb_svc = mock.MagicMock()
    mock_api.sandboxes.return_value = sb_svc

    s1 = _v1(id="a", name="n1", status="running")
    s2 = _v1(id="b", name="n2", status="stopped")
    sb_svc.sandboxes_service_list_sandboxes.return_value = V1ListSandboxesResponse(
        sandboxes=[s1, s2],
        next_page_token="npt",
        previous_page_token="ppt",
        total_size="2",
    )

    result = SandboxInstance.list(organization_id="org-z", page_token="pt", limit=10, sandbox_api=mock_api)

    assert result.total_size == 2
    assert result.next_page_token == "npt"
    assert result.previous_page_token == "ppt"
    assert len(result.sandboxes) == 2
    assert {x.sandbox_id for x in result.sandboxes} == {"a", "b"}
    sb_svc.sandboxes_service_list_sandboxes.assert_called_once_with(organization_id="org-z", page_token="pt", limit=10)


def test_sandbox_instance_write_files_uses_write_file():
    mock_api = mock.MagicMock()
    sb = SandboxInstance(_v1(id="sb-6"), sandbox_api=mock_api)
    sb.write_file = mock.MagicMock()

    sb.write_files(
        [
            WriteFileParams(path="/a", content="A"),
            WriteFileParams(path="/b", content="B"),
        ]
    )

    assert sb.write_file.call_count == 2
    sb.write_file.assert_any_call("/a", "A")
    sb.write_file.assert_any_call("/b", "B")


def test_sandbox_entry_create_forwards_to_create_sandbox():
    mock_inst = mock.MagicMock()
    with mock.patch("lightning_sdk.sandbox.sandbox.create_sandbox", return_value=mock_inst) as m_create:
        sdk = Sandbox(SandboxConfig(api_key="k", base_url="https://unit.test"))
        out = sdk.create(name="verify")

    assert out is mock_inst
    m_create.assert_called_once()
    assert m_create.call_args.kwargs["name"] == "verify"
    assert m_create.call_args.kwargs["sandbox_api"] is sdk.api


def test_sandbox_create_classmethod_forwards():
    mock_inst = mock.MagicMock()
    cfg = SandboxConfig(api_key="k", base_url="https://unit.test")
    with mock.patch("lightning_sdk.sandbox.sandbox.create_sandbox", return_value=mock_inst) as m_create:
        out = Sandbox.create(config=cfg, name="from-class", cloudspace_id="space-1")

    assert out is mock_inst
    m_create.assert_called_once()
    kw = m_create.call_args.kwargs
    assert kw["name"] == "from-class"
    assert kw["cloudspace_id"] == "space-1"
    received = kw["sandbox_api"]
    expected = cfg.api()
    assert received.config_get("api_key") == expected.config_get("api_key")
    assert received.config_get("base_url") == expected.config_get("base_url")


def test_sandbox_entry_get_and_list_use_sdk_api():
    with (
        mock.patch("lightning_sdk.sandbox.sandbox.SandboxInstance.get") as m_get,
        mock.patch("lightning_sdk.sandbox.sandbox.SandboxInstance.list") as m_list,
    ):
        sdk = Sandbox(SandboxConfig(api_key="k", base_url="https://unit.test"))
        sdk.get("sb-x")
        sdk.list(limit=3)

    m_get.assert_called_once_with("sb-x", organization_id=None, sandbox_api=sdk.api)
    m_list.assert_called_once_with(organization_id=None, page_token=None, limit=3, sandbox_api=sdk.api)


def test_configure_updates_globals_and_resets_client():
    import lightning_sdk.sandbox.base as base

    snapshot = dict(base._sandbox_config)
    try:
        with mock.patch.object(base, "_api") as mock_api:
            base.configure(api_key="unit-config-key", base_url="https://cfg.unit")
            assert base._sandbox_config.get("api_key") == "unit-config-key"
            assert base._sandbox_config.get("base_url") == "https://cfg.unit"
            mock_api.reset.assert_called_once()
    finally:
        base._sandbox_config.clear()
        base._sandbox_config.update(snapshot)
        base._api.reset()
