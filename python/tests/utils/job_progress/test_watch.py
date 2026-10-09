import io
import json
import os
import threading
import time
from datetime import datetime, timezone

import pytest

from lightning_sdk.api.logs_api import LIFECYCLE_PHASE_LABEL, LogEntry
from lightning_sdk.utils.job_progress import store, tracker
from lightning_sdk.utils.job_progress.render import JsonLinesOutput, TerminalOutput, status_line
from lightning_sdk.utils.job_progress.watch import JobWatcher

T0 = time.time() - 600
# conftest patches threading.Thread for every test; the watcher's threads were defined before that
RealThread = threading.Thread


def line(t, message, labels=None):
    return LogEntry(message=message, timestamp=datetime.fromtimestamp(T0 + t, tz=timezone.utc), labels=labels or {})


def lifecycle(t, phase, message="lifecycle"):
    return line(t, message, {LIFECYCLE_PHASE_LABEL: phase})


class FakeJob:
    """A job whose log stream plays a script; a callable step changes its status mid-stream."""

    def __init__(self, status, script=(), saved_logs=""):
        self.current = status
        self.script = list(script)
        self.saved_logs = saved_logs
        self.status_reads = 0
        self.reads_at_change = 0
        self.streams = 0

    @property
    def status(self):
        self.status_reads += 1
        return self.current

    @property
    def current_run_attempt(self):
        return 1

    @property
    def total_cost(self):
        return 0.5

    def logs(self, timestamps=False):
        return self.saved_logs

    def _follow_entries(self, *, stop=None, query=None):
        self.streams += 1
        steps, self.script = self.script, []  # a reattached stream starts after what was read
        for step in steps:
            if callable(step):
                step(self)
            else:
                yield step
        while stop is not None and not stop():
            time.sleep(0.005)


def set_status(status, wait=True):
    """Change the job's status; with ``wait``, until the watcher sees it, as a real job takes a while."""

    def step(job):
        job.current = status
        job.reads_at_change = job.status_reads
        if wait:
            polled(job)

    return step


def polled(job):
    """Wait for the watcher to check the status after the last change."""
    deadline = time.monotonic() + 5
    while job.status_reads == job.reads_at_change and time.monotonic() < deadline:
        time.sleep(0.005)


def make_watcher(tmp_path, jobs, output, **kwargs):
    watcher = JobWatcher(
        kwargs.pop("job", "train-42"),
        teamspace="org/ts",
        teamspace_id="ts-id",
        state_dir=tmp_path,
        output=output,
        job_factory=lambda name, teamspace: jobs[name],
        **kwargs,
    )
    watcher.tick, watcher.slow_poll, watcher.wake, watcher.drain_timeout = 0.02, 0.05, 0.01, 2.0
    return watcher


def run_json(tmp_path, jobs, **kwargs):
    out = io.StringIO()
    watcher = make_watcher(tmp_path, jobs, JsonLinesOutput(stream=out), **kwargs)
    code = watcher.watch()
    return code, [json.loads(x) for x in out.getvalue().splitlines()], watcher


def progress_script():
    # the lifecycle line announcing a change is what makes the watcher check the status
    script = [lifecycle(1, "queued"), set_status("Running", wait=False), lifecycle(2, "execute"), polled]
    script += [line(3, "PROGRESS_PHASE train 1/1")]
    script += [line(10 + i, f"PROGRESS {10 * i}/100") for i in range(11)]
    script += [set_status("Completed", wait=False), lifecycle(30, "terminal")]
    return script


def test_watch_streams_json_and_writes_the_shared_files(tmp_path, monkeypatch):
    monkeypatch.setenv(store.SESSION_ENV, "session-1")
    job = FakeJob("Pending", progress_script())

    code, lines, watcher = run_json(tmp_path, {"train-42": job})

    assert code == 0
    assert lines[0]["kind"] == "watching"
    assert lines[0]["run"] == "train-42"
    kinds = [x["kind"] for x in lines]
    for kind in ("started", "stage", "milestone", "done"):
        assert kind in kinds
    assert lines[-1]["kind"] == "state"
    assert lines[-1]["state"]["phase"] == "done"
    assert lines[-1]["state"]["step"] == 100
    assert "last_seen" not in lines[-1]["state"]
    assert set(lines[-1]["state"]) | {"last_seen"} == set(tracker.new_state("x"))
    assert watcher.lifecycle_seen

    state = store.read_json(tmp_path / "state" / "train-42.json")
    assert state is not None
    assert state["phase"] == "done"
    assert set(state) == set(tracker.new_state("x"))
    events = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert all(set(e) == {"ts", "run", "kind", "msg"} for e in events)
    assert [e["kind"] for e in events] == [x["kind"] for x in lines if x["kind"] != "state"]
    runfile = store.read_json(tmp_path / "runs" / "train-42.json")
    assert runfile is not None
    assert runfile["session"] == "session-1"
    assert runfile["pid"] is None
    assert runfile["jobs"][0]["teamspace"] == "org/ts"


def test_state_lines_are_throttled_and_flushed():
    now = [100.0]
    out = io.StringIO()
    stream = JsonLinesOutput(stream=out, clock=lambda: now[0])
    s = tracker.new_state("train-42")
    for step in range(5):  # five changes within one second: one line
        s["step"] = step
        stream.state(s)
        now[0] += 0.1
    stream.state(s)  # unchanged: nothing held back either
    s["updated_at"] = 1.0
    stream.state(s)  # only the write time changed: not a change
    assert [json.loads(x)["state"]["step"] for x in out.getvalue().splitlines()] == [0]
    stream.flush()
    assert len(out.getvalue().splitlines()) == 1  # the last change waits out the second
    s["step"] = 9
    stream.state(s)
    now[0] += 1.0
    stream.flush()
    s["phase"] = "done"
    stream.close(s)  # the final state is never held back
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [x["state"]["step"] for x in lines] == [0, 9, 9]
    assert lines[-1]["state"]["phase"] == "done"
    assert all(x["kind"] == "state" and x["run"] == "train-42" for x in lines)


def test_lifecycle_lines_trigger_status_checks(tmp_path):
    job = FakeJob("Pending", progress_script())
    out = io.StringIO()
    watcher = make_watcher(tmp_path, {"train-42": job}, JsonLinesOutput(stream=out))
    watcher.tick = watcher.slow_poll = 30.0  # without the lifecycle lines this run would take a minute

    started = time.monotonic()
    assert watcher.watch() == 0
    assert time.monotonic() - started < 10


@pytest.mark.parametrize(("status", "phase"), [("Failed", "failed"), ("Stopped", "stopped")])
def test_a_failed_or_stopped_job_exits_non_zero(tmp_path, status, phase):
    job = FakeJob("Running", [line(1, "PROGRESS 5/10"), line(2, "torch.OutOfMemoryError: CUDA"), set_status(status)])

    code, lines, _ = run_json(tmp_path, {"train-42": job})

    assert code == 1
    assert lines[-2]["kind"] == phase
    assert lines[-1]["state"]["phase"] == phase
    if phase == "failed":
        assert "OutOfMemoryError" in lines[-2]["msg"]


def test_a_finished_job_is_read_from_its_history(tmp_path):
    job = FakeJob("Completed", [line(i, f"PROGRESS {i}/4") for i in range(5)])

    code, lines, _ = run_json(tmp_path, {"train-42": job})

    assert code == 0
    assert lines[-1]["state"]["step"] == 4
    assert job.streams == 1


def test_a_finished_job_is_timed_by_the_platform(tmp_path):
    job = FakeJob("Completed", [line(1, "PROGRESS 4/4")])
    job.started_at = datetime.fromtimestamp(T0 - 3600, tz=timezone.utc)
    job.stopped_at = datetime.fromtimestamp(T0, tz=timezone.utc).isoformat().replace("+00:00", "Z")  # as the API has it

    _, lines, _ = run_json(tmp_path, {"train-42": job})

    assert "done in 1h00m" in lines[-2]["msg"]
    assert lines[-1]["state"]["finished_at"] == pytest.approx(T0)


def test_a_finished_job_without_api_logs_reads_its_saved_file(tmp_path):
    saved = "\n".join(f"{datetime.fromtimestamp(T0 + i, tz=timezone.utc).isoformat()} PROGRESS {i}/4" for i in range(5))
    job = FakeJob("Completed", [], saved_logs=saved)

    code, lines, _ = run_json(tmp_path, {"train-42": job})

    assert code == 0
    assert lines[-1]["state"]["step"] == 4


def test_a_relaunch_is_handed_to_the_running_watcher(tmp_path):
    store.ensure_dirs(tmp_path)
    alive = os.getppid() or os.getpid() + 1
    runfile = {"run": "train-42", "jobs": [{"kind": "job", "name": "train-42", "teamspace": "org/ts"}], "pid": alive}
    store.write_json(tmp_path / "runs" / "train-42.json", runfile)

    code, lines, _ = run_json(tmp_path, {}, job="train-42-a2", run="train-42", note="batch 32 to 16")

    assert code == 0
    assert lines[0]["kind"] == "relaunch"
    assert "batch 32 to 16" in lines[0]["msg"]
    assert lines[-1]["kind"] == "state"
    saved = store.read_json(tmp_path / "runs" / "train-42.json")
    assert saved is not None
    assert [j["name"] for j in saved["jobs"]] == ["train-42", "train-42-a2"]


def test_a_failed_run_continues_with_its_relaunch(tmp_path):
    first = FakeJob("Running", [line(i, f"PROGRESS {10 * i}/100") for i in range(6)] + [set_status("Failed")])
    second = FakeJob("Running", [line(100, "PROGRESS 30/100"), line(101, "PROGRESS 100/100"), set_status("Completed")])
    jobs = {"train-42": first, "train-42-a2": second}
    out = io.StringIO()
    watcher = make_watcher(tmp_path, jobs, JsonLinesOutput(stream=out), relaunch_wait=30)

    def relaunch():
        path = tmp_path / "runs" / "train-42.json"
        for _ in range(500):
            state = store.read_json(tmp_path / "state" / "train-42.json") or {}
            if state.get("phase") == "waiting":
                break
            time.sleep(0.01)
        runfile = store.read_json(path) or {}
        runfile["jobs"].append({"kind": "job", "name": "train-42-a2", "teamspace": "org/ts"})
        store.write_json(path, runfile)

    helper = RealThread(target=relaunch)
    helper.start()
    code = watcher.watch()
    helper.join()

    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    kinds = [x["kind"] for x in lines]
    assert code == 0
    assert "attempt-failed" in kinds
    assert kinds[-2] == "done"
    final = lines[-1]["state"]
    assert final["attempt_no"] == 2
    assert [b["kind"] for b in final["setbacks"]] == ["resume"]


def test_terminal_output_draws_a_bar_and_lists_events():
    class Tty(io.StringIO):
        encoding = "utf-8"

        def isatty(self):
            return True

    out = Tty()
    terminal = TerminalOutput(stream=out)
    s = tracker.new_state("train-42")
    tracker.on_tick(s, "Running", None, T0)
    for i in range(5):
        tracker.on_entry(s, "train-42", f"PROGRESS {10 * i}/100", T0 + i, ts=T0 + i)
    terminal.event({"msg": "train-42: started"})
    terminal.state(s)
    terminal.close(s)

    text = out.getvalue()
    assert "train-42: started\n" in text
    assert "▓▓" in text
    assert "ETA" in text
    assert text.endswith("\n")


def test_status_line_falls_back_to_ascii():
    s = tracker.new_state("train-42")
    s.update(step=5, total=10, peak=8, phase="running", setbacks=[{}], lost_s=5.0)
    line = status_line(s, T0, fancy=False)
    assert line.isascii()
    assert "#####" in line
    assert "50%" in line
