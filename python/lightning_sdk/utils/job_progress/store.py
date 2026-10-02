"""The on-disk progress state, shared with tools that only read it (a status line, a Monitor).

One folder per user, laid out as the skills' ``progress.py`` lays it out, so either can write it
and the same readers keep working:

- ``state/<run>.json``: the run's tracker state (:func:`~.tracker.new_state` keys).
- ``runs/<run>.json``: the run's chain of jobs, notes, the watcher's pid and its session.
- ``events.jsonl``: one ``{"ts", "run", "kind", "msg"}`` object per line, for every run.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


def default_state_dir() -> Path:
    """The state folder.

    ``$LIGHTNING_PROGRESS_DIR``, else ``$XDG_STATE_HOME/lightning-progress``, else
    ``~/.local/state/lightning-progress``.
    """
    env = os.environ.get("LIGHTNING_PROGRESS_DIR")
    if env:
        return Path(env)
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(Path.home(), ".local", "state")
    return Path(base) / "lightning-progress"


def ensure_dirs(d: Path) -> None:
    (d / "state").mkdir(parents=True, exist_ok=True)
    (d / "runs").mkdir(parents=True, exist_ok=True)


def session_id() -> Optional[str]:
    """The Claude Code session that started this watcher, if any; its status line shows only its runs."""
    return os.environ.get(SESSION_ENV) or None


def write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write ``data`` atomically, so a reader never sees half a file."""
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # Windows refuses to replace a file another process has open; readers close it quickly
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def append_events(d: Path, events: Iterable[Dict[str, Any]]) -> None:
    lines = "".join(json.dumps(e) + "\n" for e in events)
    if not lines:
        return
    with open(d / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(lines)


def pid_alive(pid: Optional[int]) -> bool:
    """Whether a process with this pid is running."""
    if not pid:
        return False
    if sys.platform == "win32":
        return _windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_pid_alive(pid: int) -> bool:
    # os.kill(pid, 0) on Windows sends CTRL_C_EVENT instead of probing, so ask the kernel instead
    if sys.platform != "win32":
        return False
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)
