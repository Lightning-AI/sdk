"""Live handle to a sandbox PTY (pseudo-terminal) session.

Mirrors the JavaScript ``PtyHandle`` surface (see ``js/src/pty.ts``) but exposes
a synchronous, threading-based API that fits the rest of the Python SDK.
"""

from __future__ import annotations

import contextlib
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass


def write_to_stdout(chunk: bytes) -> None:
    """Default ``on_data`` sink: write raw shell bytes to ``sys.stdout`` and flush.

    Mirrors what Node's ``process.stdout.write`` does on a TTY in the JS
    SDK. Without the explicit flush, ``sys.stdout.buffer`` is block-buffered
    (8 KB) regardless of TTY status, so users only see output when the
    buffer fills or the process exits.

    Pass ``on_data=PtyHandle.discard`` (or any no-op callable) to a
    ``PtyHandle`` constructor / ``create_pty`` call to suppress this default.
    """
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()


@dataclass
class PtySize:
    """Terminal dimensions in columns and rows."""

    cols: int
    rows: int


@dataclass
class PtyResult:
    """Result returned when a PTY session terminates.

    The Lightning xterm wire protocol does not currently propagate the SSH
    command's exit status, so ``exit_code`` is ``0`` for a clean WebSocket
    close, ``-1`` for an abnormal close, and ``None`` while the session is
    still running.
    """

    exit_code: int | None
    error: str | None


@dataclass
class PtySessionInfo:
    """Snapshot of a PTY session's state."""

    id: str
    active: bool
    cols: int | None = None
    rows: int | None = None
    cwd: str | None = None
    created_at: str | None = None
    process_id: int | None = None


class PtyHandle:
    """Live handle to a PTY session.

    A ``PtyHandle`` wraps a single WebSocket to the controlplane's
    ``/v1/clusters/{clusterId}/machines/{sandboxId}/attach`` endpoint. Frames
    from the server are raw shell bytes (combined stdout/stderr); the SDK
    forwards them verbatim to the ``on_data`` callback supplied at create
    time. Outbound input is sent as raw text frames; resize is sent as a
    JSON control frame ``{"type":"resize","cols":N,"rows":M}`` (matches the
    wire shape the Lightning UI's terminal already speaks).

    The handle is created by :meth:`SandboxProcess.create_pty` /
    :meth:`SandboxProcess.connect_pty` and is not intended to be constructed
    directly.

    To make the class easy to test in isolation, the constructor takes plain
    ``send`` / ``close`` callables and exposes ``_on_open`` / ``_on_message`` /
    ``_on_error`` / ``_on_close`` lifecycle hooks the transport is expected to
    call. The default transport in :mod:`lightning_sdk.sandbox.process` wires
    these to ``websocket.WebSocketApp``.
    """

    @staticmethod
    def discard(_chunk: bytes) -> None:
        """No-op ``on_data`` callback used to opt out of the default stdout sink."""

    def __init__(
        self,
        *,
        session_name: str,
        send: Callable[[str], None],
        close: Callable[[int, str], None],
        cols: int,
        rows: int,
        on_data: Callable[[bytes], None] | None = None,
        initial_input: list[str] | None = None,
    ) -> None:
        self.id = session_name
        self._send = send
        self._close = close
        # Default to flushing stdout so Python users get the same live-output
        # experience JS users get from `process.stdout.write` on a TTY.
        self._on_data_cb = on_data if on_data is not None else write_to_stdout
        self._initial_input = list(initial_input or [])

        self._size = PtySize(cols=cols, rows=rows)
        self._exit_code: int | None = None
        self._error: str | None = None
        self._open_error: Exception | None = None

        self._connected = False
        self._closed = False
        self._open_event = threading.Event()
        self._close_event = threading.Event()

    # -- public properties ----------------------------------------------------

    @property
    def exit_code(self) -> int | None:
        """Most recent exit code; ``None`` while the session is still running."""
        return self._exit_code

    @property
    def error(self) -> str | None:
        """Termination reason after an abnormal close; otherwise ``None``."""
        return self._error

    @property
    def size(self) -> PtySize:
        """Last terminal dimensions known to the SDK."""
        return PtySize(cols=self._size.cols, rows=self._size.rows)

    def is_connected(self) -> bool:
        """Whether the underlying WebSocket is currently OPEN."""
        return self._connected

    # -- public commands ------------------------------------------------------

    def wait_for_connection(self, timeout: float | None = None) -> None:
        """Block until the WebSocket transitions to OPEN.

        Args:
            timeout: Reject (raise :class:`TimeoutError`) if the socket hasn't
                opened within this many seconds. ``None`` waits forever.

        Raises:
            TimeoutError: If ``timeout`` elapses before the socket opens.
            RuntimeError: If the socket errored out before opening.
        """
        if self._connected:
            return
        opened = self._open_event.wait(timeout=timeout)
        if not opened:
            raise TimeoutError(f"PTY connection timed out after {timeout}s")
        if self._open_error is not None:
            raise RuntimeError(f"PTY WebSocket connection failed: {self._open_error}")
        if not self._connected and self._closed:
            # Socket closed before opening — surface a useful error.
            raise RuntimeError(self._error or "PTY WebSocket closed before opening")

    def send_input(self, data: str | bytes | bytearray) -> None:
        r"""Send input to the shell.

        Strings are forwarded verbatim; ``bytes`` / ``bytearray`` are decoded as
        UTF-8 (matches the existing handler, which treats every WebSocket frame
        as text).

        ::

            pty.send_input("ls -la\n")
            pty.send_input(b"\x03")  # Ctrl+C
        """
        if self._closed:
            raise RuntimeError("PTY session is closed")
        if not self._connected:
            self.wait_for_connection()
        payload = bytes(data).decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        self._send(payload)

    def resize(self, cols: int, rows: int) -> PtySessionInfo:
        """Resize the terminal.

        Emits the same JSON control frame the Lightning UI sends, which the
        server translates into an SSH ``WindowChange``.
        """
        if self._closed:
            raise RuntimeError("PTY session is closed")
        if not self._connected:
            self.wait_for_connection()
        import json

        self._send(json.dumps({"type": "resize", "cols": cols, "rows": rows}))
        self._size = PtySize(cols=cols, rows=rows)
        return PtySessionInfo(
            id=self.id,
            active=self._connected,
            cols=cols,
            rows=rows,
        )

    def kill(self) -> None:
        """Send Ctrl+C to the shell, then close the WebSocket.

        The remote screen session (when present) keeps running; use
        :meth:`SandboxProcess.kill_pty_session` to also tear down the screen
        session itself.
        """
        if self._closed:
            return
        # We're closing anyway, so the send failing is not actionable.
        with contextlib.suppress(Exception):
            if self._connected:
                self._send("\u0003")
        self.disconnect()

    def disconnect(self) -> None:
        """Close the WebSocket without signaling the shell.

        The underlying process keeps running on the server.
        """
        if self._closed:
            return
        # The transport may already be tearing down; either way, fall through
        # to wait on the close event below.
        with contextlib.suppress(Exception):
            self._close(1000, "client disconnect")
        self._close_event.wait()

    def wait(self, timeout: float | None = None) -> PtyResult:
        """Wait for the session to terminate.

        Returns once the WebSocket has closed (because the user typed ``exit``,
        the shell exited, or the SDK called :meth:`disconnect` / :meth:`kill`).

        Args:
            timeout: Maximum number of seconds to wait. ``None`` waits forever.

        Raises:
            TimeoutError: If ``timeout`` elapses before the session closes.
        """
        finished = self._close_event.wait(timeout=timeout)
        if not finished:
            raise TimeoutError(f"PTY session did not close within {timeout}s")
        return PtyResult(exit_code=self._exit_code, error=self._error)

    # -- transport hooks ------------------------------------------------------
    # The transport (real WebSocketApp or a fake in tests) calls these.

    def _on_open(self) -> None:
        self._connected = True
        for line in self._initial_input:
            # If the send fails the next user-facing call will surface it.
            with contextlib.suppress(Exception):
                self._send(line)
        self._open_event.set()

    def _on_message(self, data: str | bytes | bytearray) -> None:
        chunk = _to_bytes(data)
        if chunk is not None:
            self._on_data_cb(chunk)

    def _on_error(self, err: Exception) -> None:
        if not self._connected:
            self._open_error = err
            # Unblock waiters so they can see the error.
            self._open_event.set()

    def _on_close(self, code: int, reason: str) -> None:
        self._connected = False
        self._closed = True
        clean = code in (1000, 1005)
        self._exit_code = 0 if clean else -1
        if not clean:
            self._error = reason or f"WebSocket closed with code {code}"
        # Unblock both wait_for_connection and wait.
        self._open_event.set()
        self._close_event.set()


def _to_bytes(data: str | bytes | bytearray | memoryview | None) -> bytes | None:
    """Best-effort coercion of a WebSocket payload to bytes.

    The Lightning xterm protocol always sends text frames; we still accept
    ``bytes`` / ``bytearray`` / ``memoryview`` for forward compatibility.
    """
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, memoryview):
        return bytes(data)
    return None
