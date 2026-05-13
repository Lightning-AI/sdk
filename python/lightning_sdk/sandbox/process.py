"""Interactive process namespace for a sandbox: PTY sessions over WebSocket.

Mirrors the JavaScript ``SandboxProcess`` surface (see ``js/src/process.ts``):
each method either opens a WebSocket against the controlplane's
``/v1/clusters/{clusterId}/machines/{sandboxId}/attach`` endpoint (which is
bridged to the in-sandbox SSH server at port 2222) or shells out to ``screen``
via the existing ``run_command`` REST API for session bookkeeping.

Within a single SDK process every method works against a local registry.
Cross-process session persistence (i.e. ``connect_pty`` from a fresh process to
a session created elsewhere) requires the sandbox runtime image to ship
``screen`` and the gliderlabs SSH login shell to honor
``LAI_TERM_SESSION_NAME`` / ``LAI_TERM_RESTORE`` — both of which are tracked
as a follow-up to this initial parity work.
"""

from __future__ import annotations

import contextlib
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import quote, urlparse, urlunparse

from lightning_sdk.sandbox.pty import PtyHandle, PtySessionInfo

if TYPE_CHECKING:
    from lightning_sdk.sandbox.command import Command


@dataclass
class PtyCreateOpts:
    """Parameters for :meth:`SandboxProcess.create_pty`."""

    session_name: str
    cluster_id: str
    cwd: str | None = None
    envs: dict[str, str] | None = None
    cols: int | None = None
    rows: int | None = None
    on_data: Callable[[bytes], None] | None = None


@dataclass
class PtyConnectOpts:
    """Parameters for :meth:`SandboxProcess.connect_pty`."""

    on_data: Callable[[bytes], None] | None = None


@dataclass
class SandboxProcessContext:
    """Runtime context the :class:`Sandbox` passes into a :class:`SandboxProcess`.

    The PTY namespace can build URLs, authenticate, and shell out to
    ``run_command`` for session bookkeeping without importing the
    :class:`SandboxInstance` class directly (avoids a circular dependency).

    Internal — not part of the public API surface.
    """

    sandbox_id: str
    organization_id: str
    get_api_key: Callable[[], str]
    get_base_url: Callable[[], str]
    run_command: Callable[..., Command]


class _Transport(Protocol):
    """Minimal interface implemented by both the real and fake WebSocket."""

    def send(self, payload: str) -> None:
        ...

    def close(self, code: int, reason: str) -> None:
        ...


_WsFactory = Callable[
    [str, dict[str, str], "_TransportCallbacks"],
    _Transport,
]


@dataclass
class _TransportCallbacks:
    """Callbacks the transport invokes as the WebSocket changes state."""

    on_open: Callable[[], None]
    on_message: Callable[[Any], None]
    on_error: Callable[[Exception], None]
    on_close: Callable[[int, str], None]


@dataclass
class _WebSocketAppTransport:
    """Real transport backed by ``websocket-client``'s ``WebSocketApp``.

    Runs ``run_forever`` in a daemon thread so the sync SDK stays responsive.
    """

    _ws: Any
    _thread: threading.Thread

    def send(self, payload: str) -> None:
        self._ws.send(payload)

    def close(self, code: int, reason: str) -> None:
        try:
            self._ws.close(status=code, reason=reason.encode("utf-8"))
        except TypeError:
            # Older websocket-client builds use a different signature.
            self._ws.close()


def _default_ws_factory(
    url: str,
    headers: dict[str, str],
    callbacks: _TransportCallbacks,
) -> _Transport:
    """Build a real ``WebSocketApp`` transport.

    Imported lazily so users who never touch PTY don't pay the
    optional-dependency import cost.

    Set ``LIGHTNING_SDK_PTY_DEBUG=1`` to enable websocket-client's wire trace
    (handshake bytes, frame headers, etc.) — useful when the controlplane
    refuses the upgrade and the SDK appears to hang in
    :meth:`PtyHandle.wait_for_connection`.
    """
    try:
        import websocket  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "PTY support requires the 'websocket-client' package. Install with: pip install websocket-client"
        ) from e

    if os.environ.get("LIGHTNING_SDK_PTY_DEBUG"):
        websocket.enableTrace(True)

    header_lines = [f"{k}: {v}" for k, v in headers.items()]

    def _on_open(ws: Any) -> None:
        callbacks.on_open()

    def _on_message(ws: Any, msg: Any) -> None:
        callbacks.on_message(msg)

    def _on_error(ws: Any, err: Exception) -> None:
        callbacks.on_error(err)

    def _on_close(ws: Any, code: Any, reason: Any) -> None:
        callbacks.on_close(int(code) if code is not None else 1006, reason or "")

    ws_app = websocket.WebSocketApp(
        url,
        header=header_lines,
        on_open=_on_open,
        on_message=_on_message,
        on_error=_on_error,
        on_close=_on_close,
    )

    def _runner() -> None:
        # Surface any WebSocketBadStatusException / connect-time error that
        # `run_forever` swallows when it exits without firing on_error first
        # (older websocket-client versions did this on handshake failures).
        try:
            ws_app.run_forever(skip_utf8_validation=True)
        except Exception as err:
            callbacks.on_error(err)
            callbacks.on_close(1006, str(err))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return _WebSocketAppTransport(_ws=ws_app, _thread=thread)


class SandboxProcess:
    """``sandbox.process`` — interactive shell sessions on a sandbox.

    Use :attr:`SandboxInstance.process` to obtain an instance.
    """

    def __init__(
        self,
        ctx: SandboxProcessContext,
        *,
        ws_factory: _WsFactory | None = None,
    ) -> None:
        self._ctx = ctx
        self._ws_factory = ws_factory or _default_ws_factory
        # Live handles bound to this SandboxProcess, keyed by their
        # caller-chosen session name. Used to find an existing session before
        # falling back to ``screen -ls`` over ``run_command``.
        self._handles: dict[str, PtyHandle] = {}
        self._handles_lock = threading.Lock()

    # -- public API -----------------------------------------------------------

    def create_pty(self, opts: PtyCreateOpts) -> PtyHandle:
        r"""Create a new PTY session on the sandbox.

        ::

            pty = sandbox.process.create_pty(PtyCreateOpts(
                session_name="build",
                cluster_id=sandbox.cluster_id,
                cols=120,
                rows=30,
                on_data=lambda chunk: sys.stdout.buffer.write(chunk),
            ))
            pty.wait_for_connection()
            pty.send_input("npm test\n")
            result = pty.wait()
        """
        return self._open_pty(
            session_name=opts.session_name,
            cluster_id=opts.cluster_id,
            cwd=opts.cwd,
            envs=opts.envs,
            cols=opts.cols,
            rows=opts.rows,
            on_data=opts.on_data,
            restore=False,
        )

    def connect_pty(
        self,
        session_name: str,
        cluster_id: str,
        opts: PtyConnectOpts | None = None,
    ) -> PtyHandle:
        """Reattach to a PTY session that was previously created by :meth:`create_pty`.

        ::

            pty = sandbox.process.connect_pty(
                "build", sandbox.cluster_id,
                PtyConnectOpts(on_data=lambda c: sys.stdout.buffer.write(c)),
            )
        """
        return self._open_pty(
            session_name=session_name,
            cluster_id=cluster_id,
            cwd=None,
            envs=None,
            cols=None,
            rows=None,
            on_data=opts.on_data if opts else None,
            restore=True,
        )

    def list_pty_sessions(self) -> list[PtySessionInfo]:
        """List PTY sessions on the sandbox.

        Implemented as a ``screen -ls`` call via :meth:`SandboxInstance.run_command`
        so no new server endpoint is required. Returns the union of
        locally-tracked handles and remote ``screen`` sessions; locally-tracked
        handles include live ``cols``/``rows``.
        """
        remote: list[PtySessionInfo] = []
        try:
            result = self._ctx.run_command(cmd="screen", args=["-ls"])
            remote = _parse_screen_list(getattr(result, "output", "") or "")
        except Exception:
            # `screen -ls` exits non-zero when there are no sessions; the SDK
            # treats that as an empty list rather than an error.
            pass

        merged: dict[str, PtySessionInfo] = {info.id: info for info in remote}
        with self._handles_lock:
            handles = dict(self._handles)
        for sid, handle in handles.items():
            existing = merged.get(sid)
            size = handle.size
            merged[sid] = PtySessionInfo(
                id=sid,
                active=handle.is_connected(),
                cols=size.cols,
                rows=size.rows,
                cwd=existing.cwd if existing else None,
                created_at=existing.created_at if existing else None,
                process_id=existing.process_id if existing else None,
            )
        return list(merged.values())

    def get_pty_session_info(self, session_id: str) -> PtySessionInfo:
        """Look up a single PTY session.

        Raises:
            KeyError: If no session with ``session_id`` exists locally or on the sandbox.
        """
        for s in self.list_pty_sessions():
            if s.id == session_id:
                return s
        raise KeyError(f'PTY session "{session_id}" not found')

    def kill_pty_session(self, session_id: str) -> None:
        """Forcefully terminate a PTY session.

        Closes any live :class:`PtyHandle` for the session within this SDK
        process and runs ``screen -X -S {session_id} quit`` on the sandbox so
        the remote screen session (when present) is also torn down.
        """
        with self._handles_lock:
            handle = self._handles.pop(session_id, None)
        if handle is not None:
            handle.kill()
        # `screen -X` exits non-zero when the session doesn't exist or the
        # `screen` binary is missing from the runtime image. Either way, the
        # local handle (if any) has been killed already.
        with contextlib.suppress(Exception):
            self._ctx.run_command(cmd="screen", args=["-X", "-S", session_id, "quit"])

    def resize_pty_session(self, session_id: str, cols: int, rows: int) -> PtySessionInfo:
        """Resize the terminal of an active PTY session.

        Requires the session to be currently attached in this SDK process; the
        existing wire protocol carries resize as a JSON control frame on the
        open WebSocket and offers no out-of-band REST equivalent.
        """
        with self._handles_lock:
            handle = self._handles.get(session_id)
        if handle is None or not handle.is_connected():
            raise RuntimeError(
                f'PTY session "{session_id}" is not attached in this process; resize requires an active connection'
            )
        return handle.resize(cols, rows)

    # -- internals ------------------------------------------------------------

    def _open_pty(
        self,
        *,
        session_name: str,
        cluster_id: str,
        cwd: str | None,
        envs: dict[str, str] | None,
        cols: int | None,
        rows: int | None,
        on_data: Callable[[bytes], None] | None,
        restore: bool,
    ) -> PtyHandle:
        c = cols if cols is not None else 80
        r = rows if rows is not None else 24

        url = _build_attach_url(
            base_url=self._ctx.get_base_url(),
            cluster_id=cluster_id,
            sandbox_id=self._ctx.sandbox_id,
            session_name=session_name or "main-session",
            cols=c,
            rows=r,
            restore=restore,
        )
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._ctx.get_api_key()}",
        }
        if self._ctx.organization_id:
            headers["X-Lightning-Organization-Id"] = self._ctx.organization_id

        # The transport calls into these on the WebSocket thread; we forward
        # them to the handle (which uses thread-safe events for waiters).
        # `handle` is set right after the transport is built so the closures
        # below capture the eventual handle by reference.
        handle_holder: dict[str, PtyHandle] = {}

        def on_open() -> None:
            handle_holder["h"]._on_open()

        def on_message(msg: Any) -> None:
            handle_holder["h"]._on_message(msg)

        def on_error(err: Exception) -> None:
            handle_holder["h"]._on_error(err)

        def on_close(code: int, reason: str) -> None:
            handle_holder["h"]._on_close(code, reason)
            with self._handles_lock:
                current = self._handles.get(session_name)
                if current is handle_holder.get("h"):
                    self._handles.pop(session_name, None)

        callbacks = _TransportCallbacks(
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        transport = self._ws_factory(url, headers, callbacks)

        initial_input = _build_initial_input(cwd, envs)

        handle = PtyHandle(
            session_name=session_name,
            send=transport.send,
            close=transport.close,
            cols=c,
            rows=r,
            on_data=on_data,
            initial_input=initial_input,
        )
        handle_holder["h"] = handle

        with self._handles_lock:
            self._handles[session_name] = handle
        return handle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_attach_url(
    *,
    base_url: str,
    cluster_id: str,
    sandbox_id: str,
    session_name: str,
    cols: int,
    rows: int,
    restore: bool,
) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = f"/v1/clusters/{quote(cluster_id, safe='')}/machines/{quote(sandbox_id, safe='')}/attach"
    qs_pairs = [
        ("sessionName", session_name),
        ("cols", str(cols)),
        ("rows", str(rows)),
    ]
    if restore:
        qs_pairs.append(("restore", "true"))
    # Build the query string manually so the order matches the JS SDK output;
    # urlencode sorts deterministically in insertion order on 3.7+ but we keep
    # this explicit to avoid surprises.
    from urllib.parse import urlencode

    query = urlencode(qs_pairs)
    return urlunparse((scheme, parsed.netloc, path, "", query, ""))


def _build_initial_input(
    cwd: str | None,
    envs: dict[str, str] | None,
) -> list[str]:
    """Build the lines that should be flushed to the shell after WebSocket open.

    Emits ``export X=Y`` for each env var followed by an optional
    ``cd $cwd && clear``. Mirrors the Daytona convention so users see a clean
    prompt at the requested directory.
    """
    lines: list[str] = []
    if envs:
        for k, v in envs.items():
            lines.append(f"export {k}={_shell_quote(v)}\n")
    if cwd:
        lines.append(f"cd {_shell_quote(cwd)} && clear\n")
    return lines


def _shell_quote(value: str) -> str:
    """Single-quote a value for safe inclusion in a POSIX shell command."""
    return "'" + value.replace("'", "'\\''") + "'"


_SCREEN_LINE_RE = re.compile(r"^(\d+)\.([^\s]+)\s*\((Attached|Detached)\)")


def _parse_screen_list(output: str) -> list[PtySessionInfo]:
    """Parse the (text) output of ``screen -ls``.

    The format looks like::

        There is a screen on:
                12345.build       (Detached)
        1 Socket in /run/screen/S-root.

    We extract the part after the first ``.`` (the user-supplied session name)
    and infer ``active`` from the ``(Attached)`` / ``(Detached)`` tag.
    """
    sessions: list[PtySessionInfo] = []
    for raw in output.split("\n"):
        line = raw.strip()
        match = _SCREEN_LINE_RE.match(line)
        if not match:
            continue
        pid, name, state = match.group(1), match.group(2), match.group(3)
        sessions.append(
            PtySessionInfo(
                id=name,
                active=state == "Attached",
                process_id=int(pid),
            )
        )
    return sessions
