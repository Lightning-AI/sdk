from __future__ import annotations

from unittest import mock

import pytest

from lightning_sdk.api.sandbox_api import CommandResult, CommandStatus, SandboxApi
from lightning_sdk.lightning_cloud.openapi import V1ListSandboxesResponse, V1Sandbox
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.sandbox import Command, RunCommandOpts, Sandbox, SandboxConfig, WriteFileParams
from lightning_sdk.sandbox.base import SandboxInstance, _resolve_sandbox_api, create_sandbox
from lightning_sdk.sandbox.sandbox import _resolve_teamspace_id


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
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test", "organization_id": "org-1"})
    mock_sb = mock.MagicMock()
    with mock.patch.object(api, "sandboxes", return_value=mock_sb):
        pending = _v1(id="sb-1", name="n", status="pending")
        running = _v1(id="sb-1", name="n", status="running", project_id="proj-1")
        mock_sb.sandboxes_service_create_sandbox.return_value = pending
        mock_sb.sandboxes_service_get_sandbox.return_value = running

        with mock.patch("lightning_sdk.sandbox.base.time.sleep"):
            inst = create_sandbox(name="n", sandbox_api=api)

    assert inst.sandbox_id == "sb-1"
    assert inst.status == "running"
    body = mock_sb.sandboxes_service_create_sandbox.call_args[0][0]
    assert body.organization_id is None
    mock_sb.sandboxes_service_get_sandbox.assert_called_once()


def test_create_sandbox_raises_on_terminal_status():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test", "organization_id": "org-1"})
    mock_sb = mock.MagicMock()
    with mock.patch.object(api, "sandboxes", return_value=mock_sb):
        err = _v1(id="sb-1", status="error")
        mock_sb.sandboxes_service_create_sandbox.return_value = err

        with pytest.raises(RuntimeError, match="terminal state"):
            create_sandbox(name="n", sandbox_api=api)


def test_create_sandbox_omits_project_id_without_api_response():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test", "organization_id": "org-1"})
    mock_sb = mock.MagicMock()
    running = _v1(id="sb-1", name="n", status="running")
    with mock.patch.object(api, "sandboxes", return_value=mock_sb), mock.patch.dict(
        "os.environ",
        {"LIGHTNING_CLOUD_PROJECT_ID": "proj-env"},
        clear=False,
    ):
        mock_sb.sandboxes_service_create_sandbox.return_value = running
        create_sandbox(name="n", sandbox_api=api)

    body = mock_sb.sandboxes_service_create_sandbox.call_args[0][0]
    assert body.project_id is None


def test_create_sandbox_restore_omits_project_id_prefetch():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test", "organization_id": "org-1"})
    mock_sb = mock.MagicMock()
    running = _v1(id="sb-1", name="n", status="running")
    with mock.patch.object(api, "sandboxes", return_value=mock_sb):
        mock_sb.sandboxes_service_create_sandbox.return_value = running
        with mock.patch.object(api, "get_snapshot") as m_get_snap:
            create_sandbox(name="n", sandbox_api=api, snapshot_id="snap-1")

    m_get_snap.assert_not_called()
    body = mock_sb.sandboxes_service_create_sandbox.call_args[0][0]
    assert body.project_id is None
    assert body.snapshot_id == "snap-1"


def test_create_sandbox_sends_explicit_project_id():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test", "organization_id": "org-1"})
    mock_sb = mock.MagicMock()
    running = _v1(id="sb-1", name="n", status="running", project_id="proj-1")
    with mock.patch.object(api, "sandboxes", return_value=mock_sb):
        mock_sb.sandboxes_service_create_sandbox.return_value = running
        create_sandbox(name="n", sandbox_api=api, project_id="proj-1")

    body = mock_sb.sandboxes_service_create_sandbox.call_args[0][0]
    assert body.project_id == "proj-1"


def test_sandbox_instance_snapshot_omits_project_id_for_org_scoped_sandbox():
    from lightning_sdk.lightning_cloud.openapi import V1SandboxSnapshot

    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test", "organization_id": "org-1"})
    sb_svc = mock.MagicMock()
    sb_svc.sandboxes_service_create_sandbox_snapshot.return_value = V1SandboxSnapshot(id="snap-1", status="ready")

    sb = SandboxInstance(_v1(id="sb-1", organization_id="org-1"), sandbox_api=api)
    with mock.patch.object(api, "sandboxes", return_value=sb_svc):
        sb.snapshot(wait=False)

    body = sb_svc.sandboxes_service_create_sandbox_snapshot.call_args[0][0]
    assert body.project_id is None


def test_sandbox_instance_snapshot_maps_project_id_required_error():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test"})
    sb_svc = mock.MagicMock()
    exc = ApiException(status=400)
    exc.body = b'{"code":3, "message":"project id is required", "details":[]}'
    sb_svc.sandboxes_service_create_sandbox_snapshot.side_effect = exc

    sb = SandboxInstance(_v1(id="sb-1", organization_id="org-1"), sandbox_api=api)
    with mock.patch.object(api, "sandboxes", return_value=sb_svc), pytest.raises(
        RuntimeError,
        match="teamspace-scoped API key",
    ):
        sb.snapshot(wait=False)


def test_sandbox_instance_snapshot_sends_project_id_from_sandbox_row():
    from lightning_sdk.lightning_cloud.openapi import V1SandboxSnapshot

    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test"})
    sb_svc = mock.MagicMock()
    snap = V1SandboxSnapshot(id="snap-1", project_id="proj-1", status="ready")
    sb_svc.sandboxes_service_create_sandbox_snapshot.return_value = snap

    sb = SandboxInstance(_v1(id="sb-1", organization_id="org-1", project_id="proj-1"), sandbox_api=api)
    with mock.patch.object(api, "sandboxes", return_value=sb_svc):
        info = sb.snapshot(wait=False)

    body = sb_svc.sandboxes_service_create_sandbox_snapshot.call_args[0][0]
    assert body.project_id == "proj-1"
    assert info.id == "snap-1"


def test_sandbox_instance_stop_sends_project_id_from_sandbox_row():
    api = SandboxApi({"api_key": "unit-key", "base_url": "https://unit.test"})
    sb_svc = mock.MagicMock()
    stop_resp = mock.MagicMock(auto_snapshot_id="snap-auto")
    sb_svc.sandboxes_service_stop_sandbox.return_value = stop_resp

    sb = SandboxInstance(_v1(id="sb-1", organization_id="org-1", project_id="proj-on-sandbox"), sandbox_api=api)
    with mock.patch.object(api, "sandboxes", return_value=sb_svc):
        assert sb.stop() == "snap-auto"

    body = sb_svc.sandboxes_service_stop_sandbox.call_args[0][0]
    assert body.project_id == "proj-on-sandbox"


def test_sandbox_client_snapshot_helpers():
    from lightning_sdk.lightning_cloud.openapi import V1ListSandboxSnapshotsResponse, V1SandboxSnapshot

    sdk = Sandbox(SandboxConfig(api_key="unit-key", base_url="https://unit.test"))
    sb_svc = mock.MagicMock()
    snap = V1SandboxSnapshot(id="snap-1", status="ready")
    sb_svc.sandboxes_service_get_sandbox_snapshot.return_value = snap
    sb_svc.sandboxes_service_list_sandbox_snapshots.return_value = V1ListSandboxSnapshotsResponse(snapshots=[snap])

    with mock.patch.object(sdk.api, "sandboxes", return_value=sb_svc):
        assert sdk.get_snapshot("snap-1").id == "snap-1"
        assert sdk.list_snapshots()[0].id == "snap-1"
        sdk.delete_snapshot("snap-1")

    sb_svc.sandboxes_service_get_sandbox_snapshot.assert_called_once_with("snap-1")
    sb_svc.sandboxes_service_list_sandbox_snapshots.assert_called_once_with()
    sb_svc.sandboxes_service_delete_sandbox_snapshot.assert_called_once_with("snap-1")


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

    with mock.patch("lightning_sdk.sandbox.base.time.sleep"), mock.patch(
        "lightning_sdk.sandbox.base.time.monotonic",
        side_effect=lambda: next(monotonic_values),
    ), pytest.raises(TimeoutError, match="Timed out"):
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
    sdk = Sandbox(SandboxConfig(api_key="unit-key", base_url="https://unit.test"))
    sb_svc = mock.MagicMock()

    s1 = _v1(id="a", name="n1", status="running")
    s2 = _v1(id="b", name="n2", status="stopped")
    sb_svc.sandboxes_service_list_sandboxes.return_value = V1ListSandboxesResponse(
        sandboxes=[s1, s2],
        next_page_token="npt",
        previous_page_token="ppt",
        total_size="2",
    )

    with mock.patch.object(sdk.api, "sandboxes", return_value=sb_svc):
        result = sdk.list(page_token="pt", limit=10)

    assert result.total_size == 2
    assert result.next_page_token == "npt"
    assert result.previous_page_token == "ppt"
    assert len(result.sandboxes) == 2
    assert {x.sandbox_id for x in result.sandboxes} == {"a", "b"}
    sb_svc.sandboxes_service_list_sandboxes.assert_called_once_with(page_token="pt", limit=10)


def test_list_sandboxes_omits_organization_id_when_not_configured():
    sdk = Sandbox(SandboxConfig(api_key="unit-key", base_url="https://unit.test"))
    sb_svc = mock.MagicMock()
    sb_svc.sandboxes_service_list_sandboxes.return_value = V1ListSandboxesResponse(sandboxes=[])

    with mock.patch.object(sdk.api, "sandboxes", return_value=sb_svc):
        sdk.list()

    sb_svc.sandboxes_service_list_sandboxes.assert_called_once_with()


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
        out = Sandbox.create(config=cfg, name="from-class", spot=True)

    assert out is mock_inst
    m_create.assert_called_once()
    kw = m_create.call_args.kwargs
    assert kw["name"] == "from-class"
    assert kw["spot"] is True
    received = kw["sandbox_api"]
    assert received.config_get("api_key") == "k"
    assert received.config_get("base_url") == "https://unit.test"


def test_sandbox_create_without_config_uses_configured_globals():
    """Sandbox.configure() defaults must reach Sandbox.create() when no config= is passed."""
    import lightning_sdk.sandbox.base as base

    mock_inst = mock.MagicMock()
    snapshot = dict(base._sandbox_config)
    try:
        Sandbox.configure(api_key="configured-key", base_url="https://configured.unit")
        with mock.patch("lightning_sdk.sandbox.sandbox.create_sandbox", return_value=mock_inst) as m_create:
            Sandbox.create(name="from-defaults", instance_type="cpu-1")

        received = m_create.call_args.kwargs["sandbox_api"]
        assert received is base._api
        assert received.config_get("api_key") == "configured-key"
        assert received.config_get("base_url") == "https://configured.unit"
    finally:
        base._sandbox_config.clear()
        base._sandbox_config.update(snapshot)
        base._api.reset()


def test_sandbox_client_without_config_uses_configured_globals():
    """Sandbox() (the client) must honor Sandbox.configure() defaults, like Sandbox.create()."""
    import lightning_sdk.sandbox.base as base

    snapshot = dict(base._sandbox_config)
    try:
        Sandbox.configure(api_key="configured-key", base_url="https://configured.unit")
        client = Sandbox()

        assert client.api is base._api
        assert client.api.config_get("api_key") == "configured-key"
        assert client.api.config_get("base_url") == "https://configured.unit"
        assert client.config.api_key == "configured-key"
        assert client.config.base_url == "https://configured.unit"
    finally:
        base._sandbox_config.clear()
        base._sandbox_config.update(snapshot)
        base._api.reset()


def test_sandbox_client_with_config_uses_isolated_client():
    """An explicit config gets its own client, not the shared global one."""
    import lightning_sdk.sandbox.base as base

    client = Sandbox(SandboxConfig(api_key="explicit-key", base_url="https://explicit.unit"))
    assert client.api is not base._api
    assert client.api.config_get("api_key") == "explicit-key"


def test_sandbox_create_resolves_teamspace_to_project_id():
    mock_inst = mock.MagicMock()
    cfg = SandboxConfig(api_key="k", base_url="https://unit.test")
    with mock.patch("lightning_sdk.sandbox.sandbox.create_sandbox", return_value=mock_inst) as m_create, mock.patch(
        "lightning_sdk.sandbox.sandbox._resolve_teamspace_id",
        return_value="proj-1",
    ) as m_resolve:
        out = Sandbox.create(config=cfg, name="from-class", teamspace="owner/teamspace")

    assert out is mock_inst
    m_resolve.assert_called_once_with("owner/teamspace")
    assert m_create.call_args.kwargs["project_id"] == "proj-1"


def test_resolve_teamspace_id_accepts_owner_teamspace_name():
    resolved = mock.MagicMock()
    resolved.id = "proj-1"
    with mock.patch("lightning_sdk.utils.resolve._resolve_teamspace", return_value=resolved) as m_resolve:
        assert _resolve_teamspace_id("owner/teamspace") == "proj-1"

    m_resolve.assert_called_once_with("teamspace", org="owner", user=None)


def test_sandbox_entry_get_and_list_use_sdk_api():
    sdk = Sandbox(SandboxConfig(api_key="k", base_url="https://unit.test"))
    with mock.patch.object(sdk.api, "get_sandbox", return_value=_v1(id="sb-x")) as m_get, mock.patch.object(
        sdk.api,
        "list_sandboxes",
        return_value=V1ListSandboxesResponse(sandboxes=[]),
    ) as m_list:
        out = sdk.get("sb-x")
        sdk.list(limit=3)

    assert out.sandbox_id == "sb-x"
    m_get.assert_called_once_with("sb-x")
    m_list.assert_called_once_with(page_token=None, limit=3, project_id=None)


def test_sandbox_list_resolves_teamspace_to_project_id():
    sdk = Sandbox(SandboxConfig(api_key="k", base_url="https://unit.test"))
    with mock.patch.object(
        sdk.api,
        "list_sandboxes",
        return_value=V1ListSandboxesResponse(sandboxes=[]),
    ) as m_list, mock.patch("lightning_sdk.sandbox.sandbox._resolve_teamspace_id", return_value="proj-1") as m_resolve:
        sdk.list(limit=3, teamspace="owner/teamspace")

    m_resolve.assert_called_once_with("owner/teamspace")
    m_list.assert_called_once_with(page_token=None, limit=3, project_id="proj-1")


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
