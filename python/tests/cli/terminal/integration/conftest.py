"""Test fixtures for lightning terminal integration tests.

Provides a studio-like environment with isolated session storage.
Tests interact only via the CLI — the underlying session manager
is an implementation detail.
"""

from __future__ import annotations

import os
import sys

# Ensure the tests/ directory is on sys.path so that `cli.terminal.integration.X`
# imports work whether pytest is run from the repo root (`pytest tests/cli/...`)
# or from inside tests/ (`cd tests && pytest cli/...`) as CI does.
_tests_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

import contextlib
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRIPT_PATH = Path(__file__).parents[4] / "lightning_sdk" / "cli" / "terminal" / "scripts" / "lightningterminal.sh"
RC_PATH = Path(__file__).parents[4] / "lightning_sdk" / "cli" / "terminal" / "scripts" / "lightningterminal.rc"


# -- Test backend interface --


_PROMPT = "$ "  # Must match PS1/PROMPT in test_harness.{bash,zsh}rc
_POLL_INTERVAL = 0.01  # seconds between buffer polls
_POLL_TIMEOUT = 5.0  # max seconds to wait for prompt
_TERM_WIDTH = 80  # columns for pyte screen and PTY
_TERM_HEIGHT = 120  # rows — enough to capture full help output without scrolling


def wait_until(predicate, *, timeout: float = _POLL_TIMEOUT, message: str = "", snapshotter=None):
    """Poll until predicate() returns a truthy value. Returns the value.

    If snapshotter is provided, polling runs inside snapshotter.silent()
    so intermediate calls don't appear in the snapshot transcript.
    """
    import time
    from contextlib import nullcontext

    ctx = snapshotter.silent() if snapshotter is not None else nullcontext()
    deadline = time.monotonic() + timeout
    with ctx:
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(_POLL_INTERVAL)
    raise TimeoutError(message or "wait_until timed out")


class TestBackend(ABC):
    """Interface for test session backends."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def configure_env(self, env: dict, session_dir: Path) -> None:
        ...

    @abstractmethod
    def create_session(self, env: dict, name: str | None = None) -> tuple[str, str]:
        """Create a session, optionally with a terminal_name.

        Returns a tuple of ``(session_id, pid)``."""
        ...

    @abstractmethod
    def read_buffer(self, session_id: str, env: dict) -> str:
        """Read the raw screen buffer for a session."""
        ...

    @abstractmethod
    def teardown(self, env: dict) -> None:
        ...

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        ...

    @classmethod
    @abstractmethod
    def skip_reason(cls) -> str:
        ...

    def wait_for_prompt(self, session_id: str, env: dict, initial_prompt_count: int = 0) -> None:
        """Poll the session buffer until a new prompt appears.

        Waits until the number of prompt lines (matching _PROMPT) exceeds
        initial_prompt_count. Used to wait for shell init or command completion.
        """
        import time

        deadline = time.monotonic() + _POLL_TIMEOUT
        while time.monotonic() < deadline:
            buf = self.read_buffer(session_id, env)
            count = sum(1 for line in buf.splitlines() if line.rstrip() == _PROMPT.rstrip() or line.startswith(_PROMPT))
            if count > initial_prompt_count:
                return
            time.sleep(_POLL_INTERVAL)
        raise TimeoutError(
            f"Timed out waiting for prompt in session {session_id} "
            f"(expected > {initial_prompt_count} prompts, buffer: {buf[-200:]!r})"
        )

    def count_prompts(self, session_id: str, env: dict) -> int:
        """Count the number of prompt lines currently in the buffer."""
        buf = self.read_buffer(session_id, env)
        return sum(1 for line in buf.splitlines() if line.rstrip() == _PROMPT.rstrip() or line.startswith(_PROMPT))


class ScreenTestBackend(TestBackend):
    """GNU screen test backend."""

    MINIMUM_VERSION = (5, 0)

    def name(self) -> str:
        return "screen"

    def configure_env(self, env: dict, session_dir: Path) -> None:
        env["LIGHTNING_TERMINAL_SCREENDIR"] = str(session_dir)
        env["SCREENDIR"] = str(session_dir)  # Also set for direct screen commands in teardown
        env["LIGHTNING_TERMINAL_SCREENRC"] = str(FIXTURES_DIR / "studio-screenrc")
        env["LIGHTNING_TERMINAL_BACKEND"] = "screen"
        env["LIGHTNING_TERMINAL_SCRIPT"] = str(SCRIPT_PATH)
        env["LIGHTNING_TERMINAL_SKIP_MULTIUSER"] = "1"  # No zeus user in test env
        env["LIGHTNING_TERMINAL_SKIP_SETUP"] = "1"  # We create the dir ourselves
        env["LIGHTNING_TERMINAL_SKIP_NICE"] = "1"  # No need for priority in tests
        env["LIGHTNING_TERMINAL_QUIET"] = "1"  # Suppress attach hint in PTY tests

        # Set up a pseudo-home with test harness rc files. These set a
        # deterministic prompt and source lightningterminal.rc for command
        # tracking. In production, the studio's .zshrc does this instead.
        # Must NOT be inside session_dir — screen treats directories in
        # SCREENDIR as socket entries and gets confused.
        import tempfile

        home_dir = Path(tempfile.mkdtemp(prefix="lt-home-"))
        home_dir.chmod(0o700)
        shutil.copy(FIXTURES_DIR / "test_harness.zshenv", home_dir / ".zshenv")
        shutil.copy(FIXTURES_DIR / "test_harness.zshrc", home_dir / ".zshrc")
        shutil.copy(FIXTURES_DIR / "test_harness.bashrc", home_dir / ".bashrc")
        # Suppress the sudo hint from /etc/bash.bashrc which prints
        # "To run a command as administrator..." into the screen buffer
        (home_dir / ".hushlogin").touch()
        env["HOME"] = str(home_dir)
        env["ZDOTDIR"] = str(home_dir)
        env["LIGHTNING_TERMINAL_RC_PATH"] = str(RC_PATH)

    def create_session(self, env: dict, name: str | None = None) -> tuple[str, str]:
        """Create a session via the script, wait for the shell to be ready.

        Returns a tuple of ``(session_id, pid)``.
        """
        script = env.get("LIGHTNING_TERMINAL_SCRIPT", str(SCRIPT_PATH))
        cmd = [script, "new"]
        if name:
            cmd += ["--name", name]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create session: stdout={result.stdout!r} stderr={result.stderr!r}")

        session_id = ""
        pid = ""
        for line in result.stdout.splitlines():
            if line.startswith("session_id: "):
                session_id = line.partition(": ")[2]
            if line.startswith("pid: "):
                pid = line.partition(": ")[2]
        if not session_id:
            raise RuntimeError(f"No session_id in new output: {result.stdout!r}")

        # Wait for the shell to finish init (prompt appears in buffer)
        self.wait_for_prompt(session_id, env)
        return session_id, pid

    def read_buffer(self, session_id: str, env: dict) -> str:
        """Read the session buffer via lightningterminal.sh read."""
        script = env.get("LIGHTNING_TERMINAL_SCRIPT", str(SCRIPT_PATH))
        result = subprocess.run(
            [script, "read", "--id", session_id],
            env=env,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def teardown(self, env: dict) -> None:
        result = subprocess.run(
            ["screen", "-ls"],
            env=env,
            capture_output=True,
            text=True,
        )
        for line in (result.stdout + result.stderr).splitlines():
            line = line.strip()
            line_lower = line.lower()
            if line and ("detached" in line_lower or "attached" in line_lower):
                session_id = line.split("\t")[0].strip()
                if session_id:
                    subprocess.run(
                        ["screen", "-S", session_id, "-X", "quit"],
                        env=env,
                        capture_output=True,
                    )
        subprocess.run(["screen", "-wipe"], env=env, capture_output=True)

    @classmethod
    def is_available(cls) -> bool:
        version = cls._get_version()
        return version is not None and version >= cls.MINIMUM_VERSION

    @classmethod
    def skip_reason(cls) -> str:
        version = cls._get_version()
        return f"screen version: {version}, need >= {cls.MINIMUM_VERSION}"

    @staticmethod
    def _get_version() -> tuple[int, ...] | None:
        if not shutil.which("screen"):
            return None
        try:
            result = subprocess.run(["screen", "--version"], capture_output=True, text=True)
            m = re.search(r"(\d+)\.(\d+)", result.stdout + result.stderr)
            if m:
                return (int(m.group(1)), int(m.group(2)))
        except Exception:
            pass
        return None


@dataclass
class SessionInfo:
    """Details of a session created by given_session()."""

    id: str
    name: str | None


class _TrackingScreen:
    """Wraps a pyte.Screen to track newly drawn text since last checkpoint.

    Subclasses pyte.Screen and overrides draw() to log characters as they're
    written. This lets wait_for() distinguish new output from text already
    in the buffer — solving the "stale prompt" race condition.
    """

    def __init__(self, columns: int, lines: int):
        import pyte

        screen = self

        class _Inner(pyte.Screen):
            def draw(self, text):
                screen._new_chars.append(text)
                super().draw(text)

        self._pyte_screen = _Inner(columns, lines)
        self._new_chars: list[str] = []

    def checkpoint(self) -> None:
        """Clear the new-text buffer. Called after a successful wait_for match."""
        self._new_chars.clear()

    def new_text(self) -> str:
        """Return all text drawn since the last checkpoint."""
        return "".join(self._new_chars)

    @property
    def display(self):
        return self._pyte_screen.display

    @property
    def cursor(self):
        return self._pyte_screen.cursor


@dataclass
class AttachedSession:
    """A PTY attached to a screen session. Returned by attach_session().

    Wraps a pyte terminal emulator around the PTY master fd, so raw escape
    sequences are rendered into clean screen text. Use send() to type
    commands, wait_for() to wait for expected output, and snapshot() to
    capture the current screen state.
    """

    session_id: str
    process: subprocess.Popen
    master_fd: int
    _screen: object = field(default=None, repr=False)
    _stream: object = field(default=None, repr=False)
    _snapshotter: object = field(default=None, repr=False)
    _pty_label: str = field(default="", repr=False)

    def __post_init__(self):
        import pyte

        self._screen = _TrackingScreen(_TERM_WIDTH, _TERM_HEIGHT)
        self._stream = pyte.Stream(self._screen._pyte_screen)
        # Drain any initial output (screen startup sequences)
        self._drain(timeout=0.5)

    def _drain(self, timeout: float = 0.1) -> None:
        """Read all available PTY output and feed it to pyte."""
        import select

        while select.select([self.master_fd], [], [], timeout)[0]:
            try:
                data = os.read(self.master_fd, 4096)
                if data:
                    self._stream.feed(data.decode("utf-8", errors="replace"))
                else:
                    break
            except OSError:
                break

    def detach(self) -> None:
        """Detach from the session (terminates the screen -x process)."""
        self.process.terminate()
        self.process.wait()
        os.close(self.master_fd)

    def send(self, text: str) -> None:
        """Type text into the PTY (as if typing on a keyboard)."""
        os.write(self.master_fd, text.encode())
        if self._snapshotter is not None and self._pty_label:
            escaped = text.replace("\n", "\\n").replace("\r", "\\r").replace("\x03", "^C")
            self._snapshotter._transcript.append(f"# [{self._pty_label}] Send: {escaped}")

    def send_line(self, command: str) -> None:
        """Type a command and press Enter."""
        self.send(command + "\n")

    def wait_for(self, expected: str, timeout: float = _POLL_TIMEOUT, *, allow_stale: bool = False) -> list[str]:
        """Wait until expected text appears in new PTY output.

        By default (allow_stale=False), only matches text drawn since the
        last wait_for match. This prevents matching stale content that was
        already in the buffer — e.g. a prompt from before a detach.

        With allow_stale=True, searches the entire screen buffer (useful
        when checking for content you know is already present).

        Returns the non-empty screen lines at the moment the text appears.
        """
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._drain(timeout=_POLL_INTERVAL)
            if allow_stale:
                lines = self.display()
                if any(expected in line for line in lines):
                    self._screen.checkpoint()
                    return lines
            else:
                if expected in self._screen.new_text():
                    lines = self.display()
                    self._screen.checkpoint()
                    return lines
        lines = self.display()
        raise TimeoutError(
            f"Timed out waiting for {expected!r} in PTY for session {self.session_id}. "
            f"New text: {self._screen.new_text()!r}. Screen: {lines!r}"
        )

    def display(self) -> list[str]:
        """Return the current pyte screen as a list of non-empty lines."""
        self._drain(timeout=0.05)
        return [line.rstrip() for line in self._screen.display if line.rstrip()]

    def _render(self) -> str:
        """Return the current screen state as a stable text block.

        Strips trailing whitespace per line and omits empty lines.
        Used internally by build() and snapshot().
        """
        return "\n".join(self.display())

    def snapshot(self, label: str = "") -> str:
        """Capture the current screen state inline in the snapshot transcript.

        If label is provided, appears as ``# [pty1] Snapshot - label``.
        Otherwise appears as ``# [pty1] Snapshot - 1`` (auto-incrementing).
        Returns the screen text.
        """
        screen_text = self._render()
        if self._snapshotter is not None and self._pty_label:
            header_label = label or str(
                len(
                    [
                        line
                        for line in self._snapshotter._transcript
                        if line.startswith(f"# [{self._pty_label}] Snapshot")
                    ]
                )
                + 1
            )
            self._snapshotter._transcript.append(f"# [{self._pty_label}] Snapshot - {header_label}")
            if screen_text:
                self._snapshotter._transcript.append(screen_text)
            self._snapshotter._transcript.append("")
        return screen_text


# -- Backend discovery --

_ALL_BACKENDS: list[TestBackend] = [ScreenTestBackend()]
_AVAILABLE_BACKENDS: list[TestBackend] = [b for b in _ALL_BACKENDS if b.is_available()]

_require_backend = os.environ.get("LIGHTNING_TERMINAL_CI_REQUIRE_BACKEND") == "1"
if _require_backend and not _AVAILABLE_BACKENDS:
    reasons = ", ".join(f"{b.name()}: {b.skip_reason()}" for b in _ALL_BACKENDS)
    raise RuntimeError(f"LIGHTNING_TERMINAL_CI_REQUIRE_BACKEND=1 but no backend found. {reasons}")

terminal_integration = pytest.mark.skipif(
    not _AVAILABLE_BACKENDS,
    reason="no terminal backend available" + (f" ({_ALL_BACKENDS[0].skip_reason()})" if _ALL_BACKENDS else ""),
)


@dataclass
class StudioEnv:
    """An isolated studio-like environment for testing terminal commands."""

    _env: dict = field(repr=False)
    _session_dir: Path = field(repr=False)
    _backend: TestBackend = field(repr=False)
    _default_shell: str = field(default="bash", repr=False)
    _attached: list = field(default_factory=list, repr=False)
    _session_pids: list = field(default_factory=list, repr=False)

    def set_env(self, key: str, value: str) -> None:
        """Set an environment variable for all subsequent commands and sessions."""
        self._env[key] = value

    def unset_env(self, key: str) -> None:
        """Remove an environment variable for all subsequent commands and sessions."""
        self._env.pop(key, None)

    def run_script(self, *args: str, shell: str | None = None) -> subprocess.CompletedProcess:
        """Run lightningterminal.sh directly through a specific shell.

        Uses the environment's default shell unless overridden.
        """
        shell = shell or self._default_shell
        script = self._env.get("LIGHTNING_TERMINAL_SCRIPT", str(SCRIPT_PATH))
        cmd = [shell, script, *args]
        return subprocess.run(cmd, capture_output=True, text=True, env=self._env)

    def get_session_id(self, name: str) -> str:
        """Get the session_id for a named session via ls --raw."""
        ls = self.run_script("ls", "--raw")
        current_id = ""
        for line in ls.stdout.splitlines():
            if line.startswith("session_id: "):
                current_id = line.partition(": ")[2]
            if line.startswith("terminal_name: ") and line.partition(": ")[2] == name:
                return current_id
        raise ValueError(f"Session '{name}' not found in ls output:\n{ls.stdout}")

    def get_first_session_id(self) -> str:
        """Get the session_id of the first (or only) session via ls --raw."""
        ls = self.run_script("ls", "--raw")
        for line in ls.stdout.splitlines():
            if line.startswith("session_id: "):
                return line.partition(": ")[2]
        raise ValueError(f"No sessions found in ls output:\n{ls.stdout}")

    def start_pty(self, cmd: list[str]) -> AttachedSession:
        """Spawn a command on a PTY and return an AttachedSession handle.

        This is the low-level primitive for PTY interaction. Higher-level
        helpers like attach_session/init_session on the snapshotter build
        the command and call this.

        The PTY is tracked for cleanup at fixture teardown.
        """
        import fcntl
        import pty
        import struct
        import termios

        master_fd, slave_fd = pty.openpty()
        # Set PTY size to match the pyte screen so it tells screen the proper dimensions
        winsize = struct.pack("HHHH", _TERM_HEIGHT, _TERM_WIDTH, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=self._env,
        )
        os.close(slave_fd)
        handle = AttachedSession(session_id="", process=proc, master_fd=master_fd)
        self._attached.append(handle)
        return handle

    def cleanup_attached(self) -> None:
        """Detach all attached PTYs. Called by fixture teardown."""
        for handle in self._attached:
            with contextlib.suppress(OSError):
                handle.detach()
        self._attached.clear()

    def cleanup_sessions(self) -> None:
        """Kill all screen sessions created by this environment.

        Uses tracked PIDs as a fallback — even if the SCREENDIR is gone
        or screen -ls can't find the sessions, we can still kill by PID.
        """
        import signal

        for pid in self._session_pids:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGTERM)
        self._session_pids.clear()

    def count_prompts(self, session_id: str) -> int:
        """Count prompt lines in the session buffer."""
        return self._backend.count_prompts(session_id, self._env)


# -- Shell discovery --

_REQUIRED_SHELLS = ["bash", "zsh"]
_AVAILABLE_SHELLS = [s for s in _REQUIRED_SHELLS if shutil.which(s)]

if _require_backend and set(_REQUIRED_SHELLS) != set(_AVAILABLE_SHELLS):
    _missing = set(_REQUIRED_SHELLS) - set(_AVAILABLE_SHELLS)
    raise RuntimeError(
        f"LIGHTNING_TERMINAL_CI_REQUIRE_BACKEND=1 but shells missing: {_missing}. Install them in the CI image."
    )


# -- Fixtures --


def _make_studio_env(backend: TestBackend, tmp_path: Path, studio: bool = True) -> StudioEnv:
    # Use a short temp dir — screen's Unix sockets are limited to ~108 chars
    # and pytest's tmp_path is too long (screen silently fails to create sessions).
    import tempfile

    session_dir = Path(tempfile.mkdtemp(prefix="lt-"))
    session_dir.chmod(0o700)

    env = os.environ.copy()
    env["LIGHTNING_TERMINAL_STUDIO"] = "1" if studio else "0"
    env["NO_COLOR"] = "1"
    # Ensure screen sees an xterm-compatible TERM so that the screenrc
    # `termcapinfo xterm* ti@:te@` rule applies (disables alternate screen buffer).
    env["TERM"] = "xterm-256color"

    backend.configure_env(env, session_dir)

    return StudioEnv(_env=env, _session_dir=session_dir, _backend=backend)


@pytest.fixture(params=_AVAILABLE_SHELLS or ["bash"], ids=lambda s: s)
def shell(request):
    """Auto-parametrize tests across supported shells (bash, zsh)."""
    return request.param


def _backend_shell_params():
    """Generate (backend, shell) pairs for shell_env parametrization."""
    params = []
    for backend in _AVAILABLE_BACKENDS:
        for s in _AVAILABLE_SHELLS:
            params.append((backend, s))
    return params or [("none", "bash")]


@pytest.fixture(
    params=_backend_shell_params(),
    ids=lambda p: f"{p[0].name()}-{p[1]}" if isinstance(p[0], TestBackend) else "none",
)
def shell_env(request, tmp_path, snapshot):
    """A studio-like environment for testing the shell script layer.

    Parametrized across backends AND shells, so every test using this
    fixture automatically runs against both bash and zsh.

    Always wraps StudioEnv in a ShellSnapshotter so every run()
    call is recorded. The transcript is auto-asserted against a
    syrupy snapshot at teardown.
    """
    from cli.terminal.integration._helpers import ShellSnapshotter

    backend, shell = request.param
    if backend == "none":
        pytest.skip("no terminal backend available")

    studio_env = _make_studio_env(backend, tmp_path, studio=True)
    studio_env._default_shell = shell
    studio_env._env["SHELL"] = shell
    env = ShellSnapshotter(studio_env)
    yield env

    try:
        assert env.build() == snapshot
    finally:
        studio_env.cleanup_attached()
        studio_env.cleanup_sessions()
        backend.teardown(studio_env._env)
        import shutil

        shutil.rmtree(studio_env._session_dir, ignore_errors=True)


@pytest.fixture(
    params=_AVAILABLE_BACKENDS or ["none"],
    ids=lambda b: b.name() if isinstance(b, TestBackend) else b,
)
def non_studio_env(request, tmp_path):
    """An environment that simulates being outside a Lightning Studio."""
    backend = request.param
    if backend == "none":
        pytest.skip("no terminal backend available")

    return _make_studio_env(backend, tmp_path, studio=False)
