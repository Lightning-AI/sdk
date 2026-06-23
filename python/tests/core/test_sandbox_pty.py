"""Unit tests for the PTY namespace.

The Lightning controlplane attach endpoint is a live WebSocket; here we
substitute a fake transport factory so we can exercise the SDK end-to-end (URL
construction, input/resize framing, lifecycle events) without a running
server.

Mirrors ``js/tests/pty.test.ts``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from lightning_sdk.api.sandbox_api import CommandResult
from lightning_sdk.sandbox.process import (
    PtyConnectOpts,
    PtyCreateOpts,
    SandboxProcess,
    SandboxProcessContext,
    _TransportCallbacks,
)
from lightning_sdk.sandbox.pty import PtyHandle

# ---------------------------------------------------------------------------
# Tiny WebSocket stand-in
# ---------------------------------------------------------------------------


class FakeWs:
    """Captures everything the SDK pushes through the transport interface and
    exposes ``fire_*`` helpers so tests can drive the WebSocket lifecycle."""

    def __init__(self, url: str, headers: dict[str, str], callbacks: _TransportCallbacks) -> None:
        self.url = url
        self.headers = headers
        self.callbacks = callbacks
        self.sent: list[str] = []
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None

    # transport interface
    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self, code: int, reason: str) -> None:
        if self.closed:
            return
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        # Fire close synchronously — mirrors how the JS test uses
        # `queueMicrotask`. The SDK's `disconnect()` then sees the close event
        # already set when it calls `_close_event.wait()` and returns
        # immediately, just like the real transport eventually does.
        self.callbacks.on_close(code, reason)

    # test helpers
    def fire_open(self) -> None:
        self.callbacks.on_open()

    def fire_message(self, data: Any) -> None:
        self.callbacks.on_message(data)

    def fire_close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.callbacks.on_close(code, reason)


class FakeWsFactory:
    """Wraps `FakeWs` and tracks every instance for assertion in tests."""

    def __init__(self) -> None:
        self.instances: list[FakeWs] = []

    def __call__(self, url: str, headers: dict[str, str], callbacks: _TransportCallbacks) -> FakeWs:
        ws = FakeWs(url, headers, callbacks)
        self.instances.append(ws)
        return ws


# ---------------------------------------------------------------------------
# SandboxProcessContext fixture
# ---------------------------------------------------------------------------


def _ctx(
    *,
    sandbox_id: str = "sb-abc",
    organization_id: str = "org-1",
    cluster_id: str = "cluster-1",
    api_key: str = "test-key",
    base_url: str = "https://lightning.test",
    run_command: Any = None,
) -> SandboxProcessContext:
    return SandboxProcessContext(
        sandbox_id=sandbox_id,
        organization_id=organization_id,
        cluster_id=cluster_id,
        get_api_key=lambda: api_key,
        get_base_url=lambda: base_url,
        run_command=run_command or (lambda **_: CommandResult(cmd_id="x", output="", exit_code=0)),
    )


# ---------------------------------------------------------------------------
# Tests for SandboxProcess (URL + auth + flows)
# ---------------------------------------------------------------------------


def test_create_pty_builds_the_websocket_url_the_controlplane_expects() -> None:
    factory = FakeWsFactory()
    proc = SandboxProcess(_ctx(), ws_factory=factory)

    pty = proc.create_pty(PtyCreateOpts(session_name="shell", cols=100, rows=40))
    assert len(factory.instances) == 1
    ws = factory.instances[0]

    from urllib.parse import parse_qs, urlparse

    url = urlparse(ws.url)
    assert url.scheme == "wss"
    assert url.netloc == "lightning.test"
    # The sandbox itself is the "machine" the controlplane attaches to.
    assert url.path == "/v1/clusters/cluster-1/machines/sb-abc/attach"
    qs = parse_qs(url.query)
    assert qs["sessionName"] == ["shell"]
    assert qs["cols"] == ["100"]
    assert qs["rows"] == ["40"]
    assert "restore" not in qs

    assert ws.headers["Authorization"] == "Bearer test-key"
    assert ws.headers["X-Lightning-Organization-Id"] == "org-1"

    # Drain the handle so the test exits cleanly.
    ws.fire_open()
    ws.fire_close(1000)
    pty.wait()


def test_create_pty_defaults_cluster_id_to_the_sandboxs_own_cluster() -> None:
    factory = FakeWsFactory()
    proc = SandboxProcess(_ctx(cluster_id="cluster-default"), ws_factory=factory)

    pty = proc.create_pty(PtyCreateOpts(session_name="shell"))
    ws = factory.instances[0]

    from urllib.parse import urlparse

    assert urlparse(ws.url).path == "/v1/clusters/cluster-default/machines/sb-abc/attach"

    ws.fire_open()
    ws.fire_close(1000)
    pty.wait()


def test_connect_pty_defaults_cluster_id_to_the_sandboxs_own_cluster() -> None:
    factory = FakeWsFactory()
    proc = SandboxProcess(_ctx(cluster_id="cluster-default"), ws_factory=factory)

    proc.connect_pty("shell")
    ws = factory.instances[0]

    from urllib.parse import urlparse

    assert urlparse(ws.url).path == "/v1/clusters/cluster-default/machines/sb-abc/attach"


def test_connect_pty_sets_restore_true_so_the_server_reattaches() -> None:
    factory = FakeWsFactory()
    proc = SandboxProcess(
        _ctx(organization_id="", base_url="http://localhost:9800"),
        ws_factory=factory,
    )

    pty = proc.connect_pty("shell")
    ws = factory.instances[0]

    from urllib.parse import parse_qs, urlparse

    url = urlparse(ws.url)
    assert url.scheme == "ws"
    assert url.path == "/v1/clusters/cluster-1/machines/sb-abc/attach"
    qs = parse_qs(url.query)
    assert qs["sessionName"] == ["shell"]
    assert qs["restore"] == ["true"]
    # No org header when not set.
    assert "X-Lightning-Organization-Id" not in ws.headers

    ws.fire_open()
    ws.fire_close(1000)
    pty.wait()


def test_list_pty_sessions_parses_screen_ls_output() -> None:
    screen_output = "\n".join(
        [
            "There are screens on:",
            "        12345.shell    (Detached)",
            "        67890.build    (Attached)",
            "2 Sockets in /run/screen/S-root.",
            "",
        ]
    )

    calls: list[dict[str, Any]] = []

    def run_command(**kwargs: Any) -> CommandResult:
        calls.append(kwargs)
        # `screen -ls` exits non-zero when there are sessions; we don't care.
        return CommandResult(cmd_id="x", output=screen_output, exit_code=1)

    proc = SandboxProcess(
        _ctx(organization_id="", run_command=run_command),
        ws_factory=FakeWsFactory(),
    )

    sessions = proc.list_pty_sessions()
    assert calls == [{"cmd": "screen", "args": ["-ls"]}]
    assert len(sessions) == 2
    assert sessions[0].id == "shell"
    assert sessions[0].active is False
    assert sessions[0].process_id == 12345
    assert sessions[1].id == "build"
    assert sessions[1].active is True


def test_kill_pty_session_runs_screen_x_and_removes_local_handle() -> None:
    calls: list[dict[str, Any]] = []

    def run_command(**kwargs: Any) -> CommandResult:
        calls.append(kwargs)
        return CommandResult(cmd_id="x", output="", exit_code=0)

    factory = FakeWsFactory()
    proc = SandboxProcess(
        _ctx(organization_id="", run_command=run_command),
        ws_factory=factory,
    )

    pty = proc.create_pty(PtyCreateOpts(session_name="doomed"))
    ws = factory.instances[0]
    ws.fire_open()

    proc.kill_pty_session("doomed")

    # Should have sent Ctrl+C through the socket and then closed it.
    assert "\u0003" in ws.sent
    assert ws.closed is True

    # And it should have invoked screen -X to clean up the remote session.
    assert any(c.get("cmd") == "screen" and c.get("args") == ["-X", "-S", "doomed", "quit"] for c in calls)

    pty.wait()


def test_resize_pty_session_requires_an_attached_handle() -> None:
    factory = FakeWsFactory()
    proc = SandboxProcess(_ctx(), ws_factory=factory)

    with pytest.raises(RuntimeError, match="not attached in this process"):
        proc.resize_pty_session("nope", 100, 40)


def test_create_pty_and_connect_pty_pass_on_data_into_the_handle() -> None:
    factory = FakeWsFactory()
    proc = SandboxProcess(_ctx(), ws_factory=factory)

    received: list[bytes] = []
    pty = proc.create_pty(
        PtyCreateOpts(
            session_name="x",
            on_data=received.append,
        )
    )
    ws = factory.instances[0]
    ws.fire_open()
    pty.wait_for_connection()
    ws.fire_message("hello\n")
    assert received == [b"hello\n"]
    ws.fire_close(1000)
    pty.wait()

    factory.instances.clear()
    received2: list[bytes] = []
    proc.connect_pty("y", PtyConnectOpts(on_data=received2.append))
    ws2 = factory.instances[0]
    ws2.fire_open()
    ws2.fire_message(b"bytes-too\n")
    assert received2 == [b"bytes-too\n"]
    ws2.fire_close(1000)


# ---------------------------------------------------------------------------
# Tests for PtyHandle directly
# ---------------------------------------------------------------------------


def _make_handle(
    *,
    on_data: Any = None,
    initial_input: list[str] | None = None,
) -> tuple[PtyHandle, list[str], list[tuple[int, str]]]:
    """Build a PtyHandle with in-memory transport callables for inspection."""
    sent: list[str] = []
    closed: list[tuple[int, str]] = []
    handle = PtyHandle(
        session_name="x",
        send=sent.append,
        close=lambda code, reason: closed.append((code, reason)),
        cols=80,
        rows=24,
        on_data=on_data,
        initial_input=initial_input,
    )
    return handle, sent, closed


def test_pty_handle_delivers_shell_output_through_on_data_and_resolves_wait_on_clean_close() -> None:
    chunks: list[bytes] = []
    handle, _sent, _closed = _make_handle(on_data=chunks.append)

    handle._on_open()
    handle.wait_for_connection()
    assert handle.is_connected() is True

    handle._on_message("hello\n")
    handle._on_message("world\n")
    assert chunks == [b"hello\n", b"world\n"]

    # Clean close — exit_code should be 0, error should be None.
    handle._on_close(1000, "")
    result = handle.wait()
    assert result.exit_code == 0
    assert result.error is None
    assert handle.is_connected() is False


def test_pty_handle_send_input_forwards_text_frames_resize_sends_json_control_frame() -> None:
    handle, sent, _closed = _make_handle()
    handle._on_open()
    handle.wait_for_connection()

    handle.send_input("ls -la\n")
    handle.send_input(b"\x03")  # Ctrl+C, decoded as text
    handle.resize(120, 30)

    assert sent[0] == "ls -la\n"
    assert sent[1] == "\u0003"
    assert json.loads(sent[2]) == {"type": "resize", "cols": 120, "rows": 30}

    assert handle.size.cols == 120
    assert handle.size.rows == 30

    handle._on_close(1000, "")
    handle.wait()


def test_pty_handle_reports_abnormal_close_as_exit_code_minus_one_with_a_populated_error() -> None:
    handle, _sent, _closed = _make_handle()
    handle._on_open()
    handle.wait_for_connection()
    handle._on_close(1006, "remote dropped")

    result = handle.wait()
    assert result.exit_code == -1
    assert result.error == "remote dropped"
    assert handle.exit_code == -1
    assert handle.error == "remote dropped"


def test_pty_handle_flushes_envs_and_cwd_as_initial_input_lines() -> None:
    handle, sent, _closed = _make_handle(
        initial_input=["export FOO='bar baz'\n", "cd '/work dir' && clear\n"],
    )

    handle._on_open()
    handle.wait_for_connection()

    assert sent[0] == "export FOO='bar baz'\n"
    assert sent[1] == "cd '/work dir' && clear\n"

    handle._on_close(1000, "")
    handle.wait()


def test_pty_handle_send_input_after_close_raises() -> None:
    handle, _sent, _closed = _make_handle()
    handle._on_open()
    handle.wait_for_connection()
    handle._on_close(1000, "")
    handle.wait()

    with pytest.raises(RuntimeError, match="closed"):
        handle.send_input("oops\n")


def test_pty_handle_wait_for_connection_timeout() -> None:
    handle, _sent, _closed = _make_handle()
    with pytest.raises(TimeoutError):
        handle.wait_for_connection(timeout=0.05)
