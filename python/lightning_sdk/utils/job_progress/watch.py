"""The watcher behind ``lightning job watch``: follows a job's log stream into the progress state.

One log stream per job carries both the job's own lines and the server's lifecycle lines
(queued, executing, terminal, ...). Those lifecycle lines trigger a status check right away, so
while they arrive the job's status is checked only every :attr:`JobWatcher.slow_poll` seconds
instead of every :attr:`JobWatcher.tick`. Stalls are judged locally on every tick.

A *run* is a chain of attempts that survives a failed job being relaunched under a new name:
watching ``NEW --run RUN`` while RUN's watcher is alive hands NEW to it instead.
"""

import hashlib
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Tuple

from lightning_sdk.api.logs_api import LIFECYCLE_PHASE_LABEL, LogEntry
from lightning_sdk.utils.job_progress import tracker
from lightning_sdk.utils.job_progress.core import ATTEMPT_FAILED, FINAL_PHASES, fmt_duration, make_event, pct
from lightning_sdk.utils.job_progress.store import (
    append_events,
    ensure_dirs,
    pid_alive,
    read_json,
    session_id,
    write_json,
)

TERMINAL_STATUSES = ("Completed", "Failed", "Stopped")
EXIT_CODES = {"done": 0, "failed": 1, "abandoned": 1, "stopped": 1}


class Output(Protocol):
    def event(self, event: Dict[str, Any]) -> None:
        ...

    def state(self, state: Dict[str, Any], force: bool = False) -> None:
        ...

    def flush(self) -> None:
        ...

    def close(self, state: Dict[str, Any]) -> None:
        ...


class WatchedJob(Protocol):
    """What the watcher needs from a :class:`~lightning_sdk.job.Job`."""

    @property
    def status(self) -> Any:
        ...

    @property
    def current_run_attempt(self) -> Optional[int]:
        ...

    @property
    def total_cost(self) -> float:
        ...

    @property
    def logs(self) -> Any:
        ...

    def _follow_entries(
        self, *, stop: Optional[Callable[[], bool]] = None, query: Optional[str] = None
    ) -> Iterator[LogEntry]:
        ...


JobFactory = Callable[[str, Optional[str]], WatchedJob]


def same_workload(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if (a.get("kind"), a["name"]) != (b.get("kind"), b["name"]):
        return False
    if a.get("teamspace_id") and b.get("teamspace_id"):
        return a["teamspace_id"] == b["teamspace_id"]
    return a.get("teamspace") == b.get("teamspace")


def default_run(d: Path, base: str, entry: Dict[str, Any]) -> Tuple[str, bool]:
    """(run name, start fresh) for a watch without ``--run``: ``base`` unless another workload holds it.

    The same job name in two teamspaces is two runs, so a name held by another workload gets a
    qualifier. A finished run of the same workload starts over; only an explicit ``--run``
    continues one.
    """
    ident = f"{entry.get('kind')}|{entry['name']}|{entry.get('teamspace')}"
    qualifier = (entry.get("teamspace") or "default").replace("/", "-")
    digest = hashlib.sha1(ident.encode()).hexdigest()[:8]
    for run in (base, f"{base}@{qualifier}", f"{base}@{digest}"):
        runfile = read_json(d / "runs" / f"{run}.json")
        if not runfile or not runfile.get("jobs"):
            return run, True
        if same_workload(runfile["jobs"][0], entry):
            state = read_json(d / "state" / f"{run}.json") or {}
            return run, state.get("phase") in FINAL_PHASES and not pid_alive(runfile.get("pid"))
    return f"{base}@{digest}", True


class _Follower(threading.Thread):
    """Consumes one job's log stream into the shared state until the stream ends."""

    def __init__(self, job: WatchedJob, name: str, watcher: "JobWatcher") -> None:
        super().__init__(daemon=True)
        self.job, self.job_name, self.watcher = job, name, watcher
        self.abandoned = False
        self.got_entries = False
        self.error: Optional[str] = None

    def stop_requested(self) -> bool:
        return self.abandoned or self.watcher.finished.is_set()

    def run(self) -> None:
        try:
            for entry in self.job._follow_entries(stop=self.stop_requested, query=self.watcher.query):
                if self.abandoned:
                    return
                self.watcher.on_entry(self, entry)
        except Exception as ex:  # a dropped stream is restarted by the watcher
            self.error = f"{type(ex).__name__}: {ex}"


class JobWatcher:
    """Follows one run of jobs to its end, writing the state folder and reporting to ``output``."""

    tick = 5.0  # local stall checks, and status checks while no lifecycle lines arrive
    slow_poll = 30.0  # status checks while lifecycle lines report the job's changes as they happen
    cost_interval = 30.0
    drain_timeout = 30.0  # how long a finished job's stream gets to deliver its last lines
    wake = 1.0  # how often throttled output is flushed
    max_failures = 12

    def __init__(
        self,
        job: str,
        *,
        teamspace: Optional[str],
        teamspace_id: Optional[str],
        state_dir: Path,
        output: Output,
        job_factory: JobFactory,
        run: Optional[str] = None,
        note: Optional[str] = None,
        query: Optional[str] = None,
        relaunch_wait: float = 0.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.job_name = job
        self.teamspace, self.teamspace_id = teamspace, teamspace_id
        self.dir = state_dir
        self.output = output
        self.job_factory = job_factory
        self.run_name = run
        self.note = note
        self.query = query
        self.relaunch_wait = relaunch_wait
        self.clock = clock
        self.lock = threading.RLock()
        self.poll_now = threading.Event()
        self.finished = threading.Event()
        self.lifecycle_seen = False
        self.fast_polls = 0
        self.ended_at: Optional[float] = None  # when the current job stopped, by the platform's clock
        self.state: Dict[str, Any] = {}
        self.run = ""

    # -- files and output -------------------------------------------------------------------

    @property
    def run_path(self) -> Path:
        return self.dir / "runs" / f"{self.run}.json"

    @property
    def state_path(self) -> Path:
        return self.dir / "state" / f"{self.run}.json"

    def save(self, events: List[Dict[str, Any]]) -> None:
        """Write the state, append ``events``, and report both. Call with :attr:`lock` held."""
        self.state["updated_at"] = self.clock()
        write_json(self.state_path, self.state)
        append_events(self.dir, events)
        for e in events:
            self.output.event(e)
        self.output.state(self.state)

    def read_runfile(self, fallback: Dict[str, Any]) -> Dict[str, Any]:
        return read_json(self.run_path) or fallback

    # -- the run ----------------------------------------------------------------------------

    def watch(self) -> int:
        """Follow the run to its end; returns the exit code (0 once the run is done)."""
        ensure_dirs(self.dir)
        entry = {
            "kind": "job",
            "name": self.job_name,
            "teamspace": self.teamspace,
            "teamspace_id": self.teamspace_id,
            "added_at": self.clock(),
        }
        self.run, fresh = (self.run_name, False) if self.run_name else default_run(self.dir, self.job_name, entry)
        runfile = (None if fresh else read_json(self.run_path)) or {
            "run": self.run,
            "jobs": [],
            "notes": [],
            "abandoned": False,
            "pid": None,
        }
        runfile.setdefault("jobs", [])
        runfile.setdefault("notes", [])
        if not any(same_workload(j, entry) for j in runfile["jobs"]):
            runfile["jobs"].append(entry)
        if self.note:
            runfile["notes"].append({"at": self.clock(), "job": self.job_name, "note": self.note})
        runfile["abandoned"] = False
        runfile["session"] = session_id() or runfile.get("session")

        if pid_alive(runfile.get("pid")) and runfile.get("pid") != os.getpid():
            write_json(self.run_path, runfile)
            msg = f"continuing with {self.job_name}" + (f" · {self.note}" if self.note else "")
            event = make_event("relaunch", self.run, msg, self.clock())
            append_events(self.dir, [event])
            self.output.event(event)
            self.output.close(read_json(self.state_path) or tracker.new_state(self.run))
            return 0

        runfile["pid"] = os.getpid()
        write_json(self.run_path, runfile)
        state = (None if fresh else read_json(self.state_path)) or tracker.new_state(self.run)
        if state["phase"] in FINAL_PHASES or state["phase"] == "waiting":
            state["phase"] = "pending"
            state["finished_at"] = None
        self.state = state
        # marks where this watcher's part of the run starts, for a reader that starts after it
        watching = make_event("watching", self.run, f"watching {self.job_name}", self.clock())
        append_events(self.dir, [watching])
        self.output.event(watching)
        with self.lock:
            self.save([])
        try:
            self._follow_run(runfile, entry)
        finally:
            runfile = self.read_runfile(runfile)
            if runfile.get("pid") == os.getpid():
                runfile["pid"] = None
                write_json(self.run_path, runfile)
            self.output.close(self.state)
        return EXIT_CODES.get(self.state["phase"], 1)

    def _follow_run(self, runfile: Dict[str, Any], entry: Dict[str, Any]) -> None:
        state = self.state
        idx = next(i for i, j in enumerate(runfile["jobs"]) if same_workload(j, entry))
        while True:
            runfile = self.read_runfile(runfile)
            entry = runfile["jobs"][idx]
            with self.lock:
                if state["job"] and state["job"] != entry["name"]:
                    state["issue_since"] = state["issue_since"] or state["last_sample_at"]
                    state["job_running_since"] = None
                    tracker.end_attempt(state, self.clock())
                    # a new job is the next attempt, and its status and attempt numbers start over
                    tracker.open_attempt(state)
                    state.update(status=None, platform_attempt=None, closed_attempt=None)
                if state["phase"] == "waiting":
                    state["phase"] = "pending"
                state["job"] = entry["name"]
                self.save([])
            outcome = self._follow_job(entry, idx)
            runfile = self.read_runfile(runfile)
            newer = len(runfile["jobs"]) > idx + 1

            if outcome == "superseded" or (newer and outcome != "Completed"):
                idx += 1
                continue
            final = {"Completed": "done", "Stopped": "stopped"}.get(outcome)
            if final:
                with self.lock:
                    self.save([tracker.finish(state, final, self.ended_at or self.clock())])
                return

            # Failed: keep the run open until a relaunch arrives, it is abandoned, or time runs out.
            if self.relaunch_wait <= 0:
                with self.lock:
                    self.save([tracker.finish(state, "failed", self.ended_at or self.clock())])
                return
            with self.lock:
                state["phase"] = "waiting"
                state["issue_since"] = state["issue_since"] or state["last_sample_at"] or self.clock()
                cause = tracker.recent_cause(state, None)
                msg = (
                    f"{entry['name']} failed at {pct(state['step'], state['total']) or 0}%"
                    + (f" · {cause}" if cause else "")
                    + f" · waiting {fmt_duration(self.relaunch_wait)} for a relaunch"
                )
                self.save([make_event(ATTEMPT_FAILED, self.run, msg, self.clock())])
            outcome = self._wait_for_relaunch(runfile, idx)
            if outcome == "relaunched":
                idx += 1
                continue
            with self.lock:
                self.save([tracker.finish(state, "abandoned" if outcome == "abandoned" else "failed", self.clock())])
            return

    def _wait_for_relaunch(self, runfile: Dict[str, Any], idx: int) -> str:
        deadline = self.clock() + self.relaunch_wait
        while self.clock() < deadline:
            time.sleep(min(self.tick, max(0.0, deadline - self.clock())))
            runfile = self.read_runfile(runfile)
            if runfile.get("abandoned"):
                return "abandoned"
            if len(runfile["jobs"]) > idx + 1:
                return "relaunched"
            with self.lock:
                self.save([])
        return "timeout"

    # -- one job ----------------------------------------------------------------------------

    def on_entry(self, follower: _Follower, entry: LogEntry) -> None:
        """Feed one log entry from ``follower``'s stream.

        Lines from a follower that was let go of are dropped, so a stream that ends late can't
        write into the attempt after it.
        """
        with self.lock:
            if follower.abandoned:
                return
            follower.got_entries = True
            now = self.clock()
            at = entry.timestamp.timestamp() if entry.timestamp is not None else None
            phase = entry.labels.get(LIFECYCLE_PHASE_LABEL)
            if phase:
                # the server reports the job's lifecycle as it happens: check its status now
                self.lifecycle_seen = True
                self.fast_polls = 3
                if phase == "failure.reason" and entry.message:
                    self.state["last_error"] = entry.message.strip()[:120]
                    self.state["last_error_at"] = at if at is not None else now
                self.poll_now.set()
                return
            events = tracker.on_entry(self.state, follower.job_name, entry.message, now, ts=at, labels=entry.labels)
            if events or now - (self.state["updated_at"] or 0) > 1:
                self.save(events)

    def _drain_saved_logs(self, job: WatchedJob, name: str) -> None:
        """A finished job whose lines are not in the logs API: read its saved log file once."""
        try:
            text = job.logs(timestamps=True)
        except Exception as ex:
            print(f"could not read saved logs: {ex}", file=sys.stderr, flush=True)
            return
        with self.lock:
            events: List[Dict[str, Any]] = []
            for line in str(text or "").splitlines():
                events += tracker.on_line(self.state, name, line, self.clock())
            self.save(events)

    def _note_job_times(self, job: WatchedJob) -> None:
        """Take a finished job's start and stop times from the platform.

        A job that finished before (or soon after) the watcher started was never seen running,
        so its duration would otherwise be measured from the watcher's own start.
        """
        started, stopped = _epoch(getattr(job, "started_at", None)), _epoch(getattr(job, "stopped_at", None))
        with self.lock:
            if started is not None and (self.state["started_at"] is None or started < self.state["started_at"]):
                self.state["started_at"] = started
        self.ended_at = stopped

    def _follow_job(self, entry: Dict[str, Any], idx: int) -> str:
        """Check one job's status and keep its log stream attached until it ends.

        Returns its terminal status, or ``superseded`` once the run was handed a newer job.
        """
        name = entry["name"]
        job = self.job_factory(name, entry.get("teamspace") or self.teamspace)
        follower: Optional[_Follower] = None
        follower_deaths, follower_retry_at = 0, 0.0
        last_cost, terminal_since, failures = 0.0, None, 0
        next_poll, last_tick = 0.0, 0.0
        status: Optional[str] = None
        got_any, history_read = False, False  # whether the logs API had any line for this job
        self.finished.clear()
        self.lifecycle_seen = False
        self.ended_at = None
        try:
            while True:
                now = self.clock()
                if now >= next_poll or self.poll_now.is_set():
                    self.poll_now.clear()
                    try:
                        status = str(job.status)
                        attempt = job.current_run_attempt
                        cost = None
                        if now - last_cost > self.cost_interval:
                            last_cost = now
                            cost = job.total_cost
                        failures = 0
                    except Exception as ex:
                        failures += 1
                        if failures >= self.max_failures:
                            raise
                        print(f"status check failed ({failures}): {ex}", file=sys.stderr, flush=True)
                        next_poll = now + self.tick
                        self.poll_now.wait(self.tick)
                        continue
                    streaming = follower is not None and follower.is_alive()
                    slow = self.lifecycle_seen and streaming and self.fast_polls <= 0
                    self.fast_polls = max(0, self.fast_polls - 1)
                    next_poll = now + (self.slow_poll if slow else self.tick)
                    last_tick = now
                    with self.lock:
                        if cost is not None:
                            self.state["cost"] = cost
                        self.save(tracker.on_tick(self.state, status, attempt, now))
                elif status is not None and now - last_tick >= self.tick:
                    last_tick = now
                    with self.lock:  # no new status: only the stall check
                        self.save(tracker.on_tick(self.state, status, None, now))

                runfile = read_json(self.run_path) or {}
                if len(runfile.get("jobs", [])) > idx + 1:  # the run was handed a newer job
                    return "superseded"

                if status in ("Pending", "Running") and (follower is None or not follower.is_alive()):
                    if follower is not None:
                        got_any = got_any or follower.got_entries
                        if follower.error:
                            print(f"log stream dropped, reattaching: {follower.error}", file=sys.stderr, flush=True)
                        # a stream that ends at once (no live stream yet) is retried ever more slowly
                        follower_deaths = 0 if follower.got_entries else follower_deaths + 1
                        follower_retry_at = now + min(60.0, self.tick * 2**follower_deaths)
                        follower = None
                    elif now >= follower_retry_at:
                        follower = _Follower(job, name, self)
                        follower.start()

                if status in TERMINAL_STATUSES:
                    self.finished.set()  # the stream ends at its next quiet moment
                    if terminal_since is None:
                        terminal_since = now
                        self._note_job_times(job)
                    if follower is not None:
                        got_any = got_any or follower.got_entries
                    if follower is None and not got_any and not history_read:
                        history_read = True  # it finished before a stream attached: read its history once
                        follower = _Follower(job, name, self)
                        follower.start()
                    if follower is None or not follower.is_alive() or now - terminal_since > self.drain_timeout:
                        if not (got_any or (follower is not None and follower.got_entries)):
                            self._drain_saved_logs(job, name)
                        return status

                self.output.flush()
                self.poll_now.wait(self.wake)
        finally:
            # a follower that outlives this job, e.g. past the drain timeout, must not write into the next one
            if follower is not None:
                with self.lock:
                    follower.abandoned = True


def _epoch(value: Any) -> Optional[float]:
    """A platform timestamp (a ``datetime`` or an ISO-8601 string) in epoch seconds; ``None`` when unset."""
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        seconds = value.timestamp() if value is not None else None
    except (AttributeError, OSError, OverflowError, ValueError):
        return None
    return seconds if seconds and seconds > 0 else None
