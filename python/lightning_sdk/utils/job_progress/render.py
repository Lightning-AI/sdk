"""Output of ``lightning job watch``: a JSON-lines stream or a live terminal bar."""

import json
import shutil
import sys
import threading
import time
from typing import IO, Any, Callable, Dict, Optional

from lightning_sdk.utils.job_progress.core import FINAL_PHASES, bar, fmt_duration, pct

# internal de-duplication bookkeeping, large and of no use to a reader of the stream
STREAM_OMITS = ("last_seen",)
STATE_MIN_INTERVAL = 1.0


class JsonLinesOutput:
    """One JSON object per line: every event, plus ``{"kind": "state", ...}`` on a state change.

    State lines go out at most once per :data:`STATE_MIN_INTERVAL`; :meth:`close` writes the last.
    """

    def __init__(self, stream: Optional[IO[str]] = None, clock: Callable[[], float] = time.time) -> None:
        self._stream = stream
        self._clock = clock
        self._lock = threading.Lock()
        self._last_sent: Optional[str] = None
        self._last_at = 0.0
        self._pending: Optional[Dict[str, Any]] = None

    def _write(self, payload: Dict[str, Any]) -> None:
        out = self._stream or sys.stdout
        out.write(json.dumps(payload) + "\n")
        out.flush()

    def event(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._write(event)

    def state(self, state: Dict[str, Any], force: bool = False) -> None:
        snapshot = {k: v for k, v in state.items() if k not in STREAM_OMITS}
        with self._lock:
            key = json.dumps({k: v for k, v in snapshot.items() if k != "updated_at"}, sort_keys=True)
            if key == self._last_sent and not force:
                self._pending = None
                return
            now = self._clock()
            if not force and now - self._last_at < STATE_MIN_INTERVAL:
                self._pending = snapshot
                return
            self._send(snapshot, key, now)

    def _send(self, snapshot: Dict[str, Any], key: str, now: float) -> None:
        self._pending = None
        self._last_sent, self._last_at = key, now
        self._write({"kind": "state", "run": snapshot.get("run"), "ts": now, "state": snapshot})

    def flush(self) -> None:
        """Send a state change held back by the throttle, once its interval has passed."""
        with self._lock:
            if self._pending is None:
                return
            now = self._clock()
            if now - self._last_at < STATE_MIN_INTERVAL:
                return
            snapshot = self._pending
            key = json.dumps({k: v for k, v in snapshot.items() if k != "updated_at"}, sort_keys=True)
            self._send(snapshot, key, now)

    def close(self, state: Dict[str, Any]) -> None:
        """Write the final state as the last line."""
        self.state(state, force=True)


def _encodable(text: str, stream: IO[str]) -> bool:
    try:
        text.encode(getattr(stream, "encoding", None) or "ascii")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def status_line(s: Dict[str, Any], now: float, fancy: bool = True) -> str:
    """One line for a run: ``▶ run  ▓▓▓▓░░  45%  train 2/3 · ETA 3m05s · ↺1 (+1m35s) · $1.41``."""
    phase = s.get("phase") or "pending"
    head = f"{'▶' if fancy else '>'} {s.get('run')}"
    p = pct(s.get("step"), s.get("total"))
    parts = []
    if p is not None:
        drawn = bar(s["step"], max(s.get("peak") or 0, s["step"]), s["total"], chars="▓▒░" if fancy else "#=-")
        parts.append(f"{drawn} {p:3d}%")
    if s.get("stage"):
        where = f"{s['stage']} {s['stage_index']}/{s['stage_count']}" if s.get("stage_count") else s["stage"]
        parts.append(where)
    if phase in FINAL_PHASES:
        parts.append(phase)
    elif phase == "pending":
        parts.append(s.get("pending_note") or "pending")
    elif phase == "starting" and p is None:
        since = s.get("stage_since") or s.get("started_at")
        parts.append("no progress reported yet" + (f" · {fmt_duration(now - since)}" if since else ""))
    elif phase in ("stalled", "recovering", "waiting"):
        parts.append(phase)
    if s.get("eta_s") is not None and phase not in FINAL_PHASES:
        parts.append(f"ETA {fmt_duration(s['eta_s'])}")
    if (s.get("attempt_no") or 1) > 1:
        parts.append(f"attempt {s['attempt_no']}")
    if s.get("setbacks"):
        parts.append(f"{'↺' if fancy else 'setbacks '}{len(s['setbacks'])} (+{fmt_duration(s.get('lost_s'))})")
    if s.get("cost") is not None and phase != "pending":
        parts.append(f"${s['cost']:.2f}")
    return f"{head}  " + (" · " if fancy else " | ").join(parts)


class TerminalOutput:
    """Events as lines, under a bar redrawn in place when the output is a terminal."""

    def __init__(self, stream: Optional[IO[str]] = None, clock: Callable[[], float] = time.time) -> None:
        self._stream = stream or sys.stdout
        self._clock = clock
        self._lock = threading.Lock()
        self._live = bool(getattr(self._stream, "isatty", lambda: False)())
        self._fancy = _encodable("▶▓▒░·↺…", self._stream)
        self._bar = ""
        self._state: Optional[Dict[str, Any]] = None

    def _text(self, text: str) -> str:
        if self._fancy:
            return text
        for a, b in (("·", "|"), ("↺", "R"), ("…", "..."), ("▶", ">")):
            text = text.replace(a, b)
        enc = getattr(self._stream, "encoding", None) or "ascii"
        return text.encode(enc, "replace").decode(enc)

    def _clear(self) -> None:
        if self._bar:
            self._stream.write("\r" + " " * len(self._bar) + "\r")
            self._bar = ""

    def _draw(self) -> None:
        if not self._live or self._state is None:
            return
        width = max(20, shutil.get_terminal_size((100, 20)).columns - 1)
        line = self._text(status_line(self._state, self._clock(), self._fancy))[:width]
        self._clear()
        self._stream.write(line)
        self._bar = line

    def event(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._clear()
            self._stream.write(self._text(str(event.get("msg", ""))) + "\n")
            self._draw()
            self._stream.flush()

    def state(self, state: Dict[str, Any], force: bool = False) -> None:
        with self._lock:
            self._state = state
            self._draw()
            self._stream.flush()

    def flush(self) -> None:
        # redraw, so elapsed times keep moving while nothing new arrives
        if self._state is not None:
            self.state(self._state)

    def close(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._state = state
            if self._live:
                self._draw()
                self._stream.write("\n")
                self._bar = ""
            else:
                self._stream.write(self._text(status_line(state, self._clock(), self._fancy)) + "\n")
            self._stream.flush()
