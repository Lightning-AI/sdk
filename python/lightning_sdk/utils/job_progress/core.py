"""Shared constants and formatting for job progress."""

from typing import Any, Dict, Optional

BAR_WIDTH = 20
FINAL_PHASES = ("done", "failed", "stopped", "abandoned")
# one attempt failed and the run waits for a relaunch; not final, so a reader keeps following it
ATTEMPT_FAILED = "attempt-failed"


def fmt_duration(seconds: Optional[float]) -> str:
    """Render a duration compactly: ``45s``, ``3m05s``, ``2h10m``; ``…`` when unknown."""
    if seconds is None:
        return "…"
    s = max(0, round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def pct(step: Optional[int], total: Optional[int]) -> Optional[int]:
    """Whole percent of ``step`` out of ``total``, clamped to 0..100; ``None`` when unknown."""
    if step is None or not total:
        return None
    return max(0, min(100, int(100 * step / total)))


def bar(step: int, peak: int, total: int, width: int = BAR_WIDTH, chars: str = "▓▒░") -> str:
    """``▓`` done now, ``▒`` ground lost to a setback (current to peak), ``░`` still to do."""
    done, lost, todo = chars[0], chars[1], chars[2]
    cur = max(0, min(width, round(width * step / total)))
    top = max(cur, min(width, round(width * peak / total)))
    return done * cur + lost * (top - cur) + todo * (width - top)


def make_event(kind: str, run: str, msg: str, at: float) -> Dict[str, Any]:
    """An entry of ``events.jsonl``: ``{"ts", "run", "kind", "msg"}``."""
    return {"ts": at, "run": run, "kind": kind, "msg": f"{run}: {msg}"}
