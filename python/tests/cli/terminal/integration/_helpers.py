"""Shared test helpers for terminal integration tests."""

from __future__ import annotations

import re
import subprocess

from cli.terminal.integration.conftest import StudioEnv

_PID_WIDTH = 7  # Max PID width on Linux (pid_max up to 4194304)


def _mask_groups(pattern: str, text: str) -> str:
    r"""Replace captured groups with X's of matching width, preserving uncaptured text.

    Example:
        _mask_groups(r"(\d+)d (\d+)h", "3d 2h")  → "Xd Xh"
        _mask_groups(r"term-(\d+)", "term-1234567")  → "term-XXXXXXX"
    """

    def _replace(match: re.Match[str]) -> str:
        result = match.group(0)
        for i in range(match.lastindex or 0, 0, -1):
            start = match.start(i) - match.start(0)
            end = match.end(i) - match.start(0)
            replacement = "X" * (end - start)
            result = result[:start] + replacement + result[end:]
        return result

    return re.sub(pattern, _replace, text)


def stable_output(output: str) -> str:
    """Replace dynamic values (PIDs, session IDs, timestamps) for stable snapshots.

    ANSI escape codes are protected first, so no regex accidentally matches
    digits inside colour codes. Captured groups are replaced with X's of
    matching width to preserve table column alignment.
    """
    # Step 1: Protect ANSI escape codes
    ansi_codes: list[str] = []

    def _save_ansi(match: re.Match[str]) -> str:
        ansi_codes.append(match.group(0))
        return f"\x00ANSI{len(ansi_codes) - 1}\x00"

    output = re.sub(r"\x1b\[[0-9;]*m", _save_ansi, output)

    # Step 2: Replace dynamic values (specific patterns before general)

    # Absolute script paths → just the script name (consistent across environments)
    output = re.sub(r"[^\s]*?/lightningterminal\.sh", "lightningterminal.sh", output)

    # Session IDs contain hex suffixes (e.g. backend-8fd461bd, session-a7f3b2c1).
    # Only mask the hex suffix, not the name part.
    output = _mask_groups(r"\w+-([0-9a-f]{8})", output)

    # Internal test session IDs: _ts0001 → _tsXXXX (fixed length, just mask digits)
    output = _mask_groups(r"_ts(\d{4})", output)

    # ISO timestamps with optional nanoseconds:
    #   2026-04-08T12:00:00.123456789+00:00 → XXXX-XX-XXTXX:XX:XX.XXXXXXXXX+XX:XX
    #   2026-04-08T12:00:00+00:00 → XXXX-XX-XXTXX:XX:XX+XX:XX
    output = _mask_groups(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d+)\+(\d{2}):(\d{2})", output)
    output = _mask_groups(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\+(\d{2}):(\d{2})", output)

    # Relative ages: 3d 2h → Xd Xh, 5h 12m → Xh XXm, 45m → XXm, just now → XXXXXXXX
    output = _mask_groups(r"(\d+)d (\d+)h", output)
    output = _mask_groups(r"(\d+)d", output)
    output = _mask_groups(r"(\d+)h (\d+)m", output)
    output = _mask_groups(r"(\d+)h", output)
    output = _mask_groups(r"(\d+)m", output)
    output = _mask_groups(r"(just now)", output)

    # Standalone PIDs → fixed _PID_WIDTH X's, absorbing trailing spaces to compensate.
    # One regex per length so we never exceed _PID_WIDTH total chars.
    # 3-digit PID + 4 spaces → 7 X's:  "123    " → "XXXXXXX"
    # 4-digit PID + 3 spaces → 7 X's:  "1234   " → "XXXXXXX"
    # 5-digit PID + 2 spaces → 7 X's:  "12345  " → "XXXXXXX"
    # 6-digit PID + 1 space  → 7 X's:  "123456 " → "XXXXXXX"
    # 7-digit PID + 0 spaces → 7 X's:  "1234567" → "XXXXXXX"
    # In table contexts, PIDs are space-padded to column width.
    # Replace PID + trailing spaces as a fixed _PID_WIDTH block.
    _x7 = "X" * _PID_WIDTH
    output = re.sub(r"(?<!\w)\d{3} {4}", _x7, output)
    output = re.sub(r"(?<!\w)\d{4} {3}", _x7, output)
    output = re.sub(r"(?<!\w)\d{5} {2}", _x7, output)
    output = re.sub(r"(?<!\w)\d{6} ", _x7, output)
    output = re.sub(r"(?<!\w)\d{7}(?!\w)", _x7, output)
    # In JSON/plain contexts, PIDs have no trailing spaces.
    # Still normalise to fixed _PID_WIDTH so snapshots don't flap with PID length.
    output = re.sub(r"(?<!\w)\d{3,7}(?!\w)", _x7, output)

    # Step 3: Restore ANSI escape codes
    for i, code in enumerate(ansi_codes):
        output = output.replace(f"\x00ANSI{i}\x00", code)

    return output


class RunResult:
    """Wraps subprocess.CompletedProcess with convenience methods."""

    def __init__(self, result: subprocess.CompletedProcess) -> None:
        self._result = result

    @property
    def stdout(self) -> str:
        return self._result.stdout

    @property
    def stderr(self) -> str:
        return self._result.stderr

    @property
    def returncode(self) -> int:
        return self._result.returncode

    def as_json(self):
        import json

        return json.loads(self.stdout)


class _BaseSnapshotter:
    """Base for snapshotters that record a transcript of commands and output.

    Subclasses implement _execute() and _cmd_prefix to control how commands
    are run and how they appear in the transcript.
    """

    def __init__(self, env: StudioEnv) -> None:
        self._env = env
        self._transcript: list[str] = []
        self._cmd_prefix = ""
        self._pty_counter: int = 0
        self._silent: int = 0

    def set_env(self, key: str, value: str) -> None:
        """Set an environment variable for all subsequent commands and sessions."""
        self._env.set_env(key, value)

    def unset_env(self, key: str) -> None:
        """Remove an environment variable for all subsequent commands and sessions."""
        self._env.unset_env(key)

    def comment(self, *lines: str) -> None:
        """Add a comment block to the snapshot transcript.

        Each line is prefixed with ``# ``. Use this to document things
        that are verified by assertions but not visible in the snapshot
        (e.g. content erased by screen's redraw).
        """
        for line in lines:
            self._transcript.append(f"# {line}" if line else "#")

    def _execute(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        """Execute the command. Subclasses override this."""
        raise NotImplementedError

    def _record(self, args: tuple[str, ...], result: subprocess.CompletedProcess) -> None:
        """Record a command and its output in the transcript."""
        if self._silent > 0:
            return
        cmd_line = " ".join(args)
        self._transcript.append(f"# Execute: {self._cmd_prefix}{cmd_line}")
        has_body = False
        if result.stdout.strip():
            self._transcript.append(result.stdout.rstrip())
            has_body = True
        if result.stderr.strip():
            for line in result.stderr.rstrip().splitlines():
                self._transcript.append(f"[STDERR] {line}")
            has_body = True
        if result.returncode != 0:
            self._transcript.append(f"exit: {result.returncode}")
            has_body = True
        if has_body:
            self._transcript.append("")

    def silent(self):
        """Context manager to suppress snapshot recording.

        Usage::

            with shell_env.silent():
                result = shell_env.run("status", session.id)
        """
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            self._silent += 1
            try:
                yield
            finally:
                self._silent -= 1

        return _ctx()

    def wait_until(self, predicate, *, timeout: float | None = None, message: str = ""):
        """Poll until predicate() returns truthy, without recording to snapshot."""
        from cli.terminal.integration.conftest import _POLL_TIMEOUT
        from cli.terminal.integration.conftest import wait_until as _wait_until

        return _wait_until(predicate, timeout=timeout or _POLL_TIMEOUT, message=message, snapshotter=self)

    def run(self, *args: str, **kwargs) -> RunResult:
        """Run a command. Asserts exit code 0."""
        result = self._execute(*args, **kwargs)
        self._record(args, result)
        assert (
            result.returncode == 0
        ), f"{self._cmd_prefix}{args[0]} failed (exit {result.returncode}):\n{result.stderr}"
        return RunResult(result)

    def run_expect_error(self, *args: str, **kwargs) -> RunResult:
        """Run a command that is expected to fail. Asserts exit code != 0."""
        result = self._execute(*args, **kwargs)
        self._record(args, result)
        assert result.returncode != 0, f"{self._cmd_prefix}{args[0]} unexpectedly succeeded:\n{result.stdout}"
        return RunResult(result)

    def given_session(self, *, name: str | None = None, attached: bool = False):
        """Set up a session before the test begins and record it in the transcript.

        Creates a session via the backend and waits for the shell to be ready.
        If attached=True, also attaches a PTY so the session shows as 'attached'.
        Use this for test arrangement — tests that are *testing* session
        creation should use ``run("new", ...)`` instead.
        """
        from cli.terminal.integration.conftest import SCRIPT_PATH, SessionInfo

        session_id, pid = self._env._backend.create_session(self._env._env, name=name)
        if pid and pid != "unknown":
            self._env._session_pids.append(int(pid))
        if attached:
            script = self._env._env.get("LIGHTNING_TERMINAL_SCRIPT", str(SCRIPT_PATH))
            self._env.start_pty([self._env._default_shell, script, "attach", "--id", session_id])
        parts = []
        parts.append(f'name="{name}"' if name else "name=<anon>")
        if attached:
            parts.append("attached=True")
        self._transcript.append(f"# Given session ({', '.join(parts)})")
        return SessionInfo(id=session_id, name=name)

    def _next_pty_label(self) -> str:
        self._pty_counter += 1
        return f"pty{self._pty_counter}"

    def _wire_pty(self, handle, label: str) -> None:
        """Wire a PTY handle into the snapshot system."""
        handle._snapshotter = self
        handle._pty_label = label

    def _script_path(self) -> str:
        from cli.terminal.integration.conftest import SCRIPT_PATH

        return self._env._env.get("LIGHTNING_TERMINAL_SCRIPT", str(SCRIPT_PATH))

    def attach_session(self, session_id: str | None = None, *, name: str | None = None, source: str | None = None):
        """Attach to a session via PTY and record it in the transcript.

        Either session_id or name must be provided. If the session doesn't
        exist, attach will create it.

        Use ``handle.snapshot(label)`` to capture the PTY screen state
        at specific moments during the test.
        """
        shell = self._env._default_shell
        script = self._script_path()
        cmd = [shell, script, "attach"]
        if session_id:
            cmd += ["--id", session_id]
        if name:
            cmd += ["--name", name]
        if source:
            cmd += ["--source", source]
        handle = self._env.start_pty(cmd)
        handle.session_id = session_id or ""
        label = self._next_pty_label()
        self._wire_pty(handle, label)
        # Transcript shows the command as run
        cmd_display = " ".join(cmd[2:])  # skip shell and script path
        self._transcript.append(f"# [{label}] Start: {shell} {script} {cmd_display}")
        return handle

    def init_session(self, session_id: str | None = None, *, source: str | None = None):
        """Create a session via ``exec lightningterminal.sh attach --exec`` on a PTY.

        Mimics how .lightningrc replaces the login shell with a
        terminal session.
        """
        shell = self._env._default_shell
        script = self._script_path()
        cmd_str = f"exec {script} attach --exec"
        if session_id:
            cmd_str += f" --id {session_id}"
        if source:
            cmd_str += f" --source {source}"
        handle = self._env.start_pty([shell, "-c", cmd_str])
        handle.session_id = session_id or ""
        label = self._next_pty_label()
        self._wire_pty(handle, label)
        self._transcript.append(f'# [{label}] Start: {shell} -c "{cmd_str}"')
        return handle

    def build(self) -> str:
        """Return the stabilised transcript for snapshot comparison."""
        return stable_output("\n".join(self._transcript) + "\n")


class ShellSnapshotter(_BaseSnapshotter):
    """Snapshotter for lightningterminal.sh (shell script layer).

    Usage::

        def test_lifecycle(self, shell_env):
            shell_env.given_session(name="Backend")
            shell_env.run("ls")
            sid = shell_env.get_session_id("Backend")
            shell_env.run("kill", sid)
            shell_env.run("ls")
            # snapshot assertion happens automatically at teardown
    """

    def __init__(self, env: StudioEnv) -> None:
        super().__init__(env)
        shell = env._default_shell
        self._cmd_prefix = f"SHELL={shell} {shell} lightningterminal.sh "

    def _execute(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        return self._env.run_script(*args, **kwargs)

    def run(self, *args: str, wait_for_completion: bool = False, **kwargs) -> RunResult:
        """Run a lightningterminal.sh command. Asserts exit code 0.

        If wait_for_completion is True and the command is 'send', polls the
        session buffer until a new prompt appears.
        """
        # For send with wait_for_completion, snapshot the prompt count before.
        # Args format: ("send", "--id", session_id, command...) or
        #              ("send", "--name", name, command...)
        prompt_count = 0
        session_id = ""
        if wait_for_completion and len(args) >= 3 and args[0] == "send":
            if args[1] == "--id":
                session_id = args[2]
            elif args[1] == "--name":
                session_id = self._env.get_session_id(args[2])
            if session_id:
                prompt_count = self._env.count_prompts(session_id)

        result = self._execute(*args, **kwargs)
        self._record(args, result)
        assert (
            result.returncode == 0
        ), f"lightningterminal.sh {args[0]} failed (exit {result.returncode}):\n{result.stderr}"

        if wait_for_completion and session_id and result.returncode == 0:
            self._env._backend.wait_for_prompt(session_id, self._env._env, prompt_count)

        return RunResult(result)

    def get_session_id(self, name: str) -> str:
        return self._env.get_session_id(name)

    def get_first_session_id(self) -> str:
        return self._env.get_first_session_id()
