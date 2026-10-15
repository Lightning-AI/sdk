import json
from datetime import datetime, timezone

import pytest

from lightning_sdk.utils.job_progress import core, tracker
from lightning_sdk.utils.job_progress.render import status_line

T0 = 1_800_000_000.0


def ts(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


class Run:
    """Drives a tracker the way the watcher does, with explicit clock values."""

    def __init__(self, name="train-42"):
        self.s = tracker.new_state(name)
        self.events = []
        self.tick("Running", T0)

    def line(self, t, text, job="train-42"):
        self.events += tracker.on_line(self.s, job, f"{ts(t)} {text}", t)

    def entry(self, t, text, labels=None, job="train-42"):
        self.events += tracker.on_entry(self.s, job, text, t, ts=t, labels=labels)

    def tick(self, status, t, attempt=None):
        self.events += tracker.on_tick(self.s, status, attempt, t)

    def kinds(self):
        return [e["kind"] for e in self.events]


# -- parsing -------------------------------------------------------------------------------


def test_progress_line():
    r = tracker.parse_progress("PROGRESS 450/1000 attempt=2 loss=0.3")
    assert r is not None
    assert (r["step"], r["total"], r["attempt"], r["source"]) == (450, 1000, 2, "progress")


def test_tqdm_last_redraw_wins():
    line = " 10%|█         | 100/1000 [00:10<01:30]\r 45%|████▌     | 450/1000 [00:45<00:55, 10it/s]"
    r = tracker.parse_progress(line)
    assert r is not None
    assert (r["step"], r["total"], r["source"]) == (450, 1000, "tqdm")


def test_tqdm_epoch_and_validation():
    r = tracker.parse_progress("Epoch 3:  40%|████      | 40/100 [00:04<00:06]")
    assert r is not None
    assert r["epoch"] == 3
    assert tracker.parse_progress("Validation DataLoader 0:  50%|█████     | 5/10 [00:01<00:01]") is None


def test_error_lines():
    assert tracker.parse_error("Traceback (most recent call last):") is None
    assert "OutOfMemoryError" in (tracker.parse_error("torch.OutOfMemoryError: CUDA out of memory.") or "")
    assert tracker.parse_error("step 10 loss 0.4") is None


def test_allocator_warning_is_not_an_error():
    warn = (
        "[W924 14:51:32.327618612 CUDACachingAllocator.cpp:3933] memory allocation failed "
        "with OOM on device 0 while trying to allocate"
    )
    assert tracker.parse_error(warn) is None
    assert tracker.parse_error("UserWarning: out of memory fallback in use") is None


def test_bar_and_durations():
    assert core.bar(6, 9, 20, width=20) == "▓" * 6 + "▒" * 3 + "░" * 11
    assert core.fmt_duration(160) == "2m40s"
    assert core.fmt_duration(3900) == "1h05m"


# -- progress ------------------------------------------------------------------------------


def test_eta_and_milestones():
    r = Run()
    for i in range(60):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/1000")
    assert r.s["phase"] == "running"
    assert r.s["rate"] == pytest.approx(1.0)
    assert r.s["eta_s"] == pytest.approx(410.0)
    milestones = [e["msg"].split(" · ")[0] for e in r.events if e["kind"] == "milestone"]
    assert milestones == [f"train-42: {p}%" for p in (10, 20, 30, 40, 50)]


def test_reconnect_replay_is_ignored():
    r = Run()
    for _ in range(2):  # a reconnect replays history from the start
        for i in range(5):
            r.line(T0 + i, f"PROGRESS {i + 1}/10")
    assert r.s["step"] == 5
    assert r.s["setbacks"] == []


def test_lines_sharing_a_timestamp_are_all_read_once():
    r = Run()
    for _ in range(2):
        r.line(T0 + 5, "PROGRESS_PHASE train")
        r.line(T0 + 5, "PROGRESS 3/10")
    assert r.s["step"] == 3
    assert r.kinds().count("stage") == 1


def test_stall_then_recovery():
    r = Run()
    for i in range(10):
        r.line(T0 + 10 * i, f"PROGRESS {i}/100")
    r.line(T0 + 95, "RuntimeError: NCCL watchdog timeout")
    r.tick("Running", T0 + 100)
    assert r.s["phase"] != "stalled"
    r.tick("Running", T0 + 90 + 121)
    assert r.s["phase"] == "stalled"
    assert "NCCL" in r.events[-1]["msg"]
    r.line(T0 + 400, "PROGRESS 10/100")
    assert r.kinds()[-2:] == ["recovered", "milestone"]
    assert r.s["setbacks"] == []  # a stall that resumes in place is not a setback
    assert r.s["lost_s"] == pytest.approx(310.0)


def test_reestimated_total_is_not_a_setback():
    r = Run()
    for i in range(1, 8):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/{300 - 5 * i}")
    assert r.s["setbacks"] == []
    assert (r.s["step"], r.s["total"]) == (70, 265)


# -- setbacks ------------------------------------------------------------------------------


def test_partial_regression_in_same_job():
    r = Run()
    for i in range(46):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/1000")
    r.line(T0 + 455, "ValueError: loss is NaN, rolling back")
    r.line(T0 + 500, "PROGRESS 300/1000")
    sb = r.s["setbacks"][-1]
    assert (sb["kind"], sb["from"], sb["to"], sb["peak"]) == ("resume", 450, 300, 450)
    assert "NaN" in sb["cause"]
    assert r.s["phase"] == "recovering"
    assert r.s["eta_s"] is None
    assert "▒" in status_line(r.s, T0 + 500)
    for i in range(1, 20):
        r.line(T0 + 500 + 10 * i, f"PROGRESS {300 + 10 * i}/1000")
    assert r.s["phase"] == "running"
    assert r.s["peak"] == 490  # passing the old peak clears the lost ground
    line = status_line(r.s, T0 + 700)
    assert "▒" not in line
    assert "↺1" in line


def test_failure_then_resume_in_new_job():
    r = Run()
    for i in range(46):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/1000")
    r.line(T0 + 455, "torch.OutOfMemoryError: CUDA out of memory")
    r.s["phase"], r.s["issue_since"] = "pending", T0 + 450
    r.s["job"], r.s["job_running_since"] = "train-42-a2", None
    r.tick("Pending", T0 + 600)
    r.tick("Running", T0 + 700)
    r.tick("Running", T0 + 900)
    assert r.s["phase"] != "stalled"  # a relaunch gets time to start
    r.line(T0 + 950, "PROGRESS 400/1000 attempt=2", job="train-42-a2")
    sb = r.s["setbacks"][-1]
    assert (sb["kind"], sb["to"]) == ("resume", 400)
    assert sb["lost_s"] == pytest.approx(500.0)
    assert "out of memory" in sb["cause"]


def test_failure_then_restart_from_scratch():
    r = Run()
    for i in range(46):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/1000")
    r.line(T0 + 1000, "PROGRESS 0/1000", job="train-42-a2")
    assert r.s["setbacks"][-1]["kind"] == "restart"


def test_new_setup():
    r = Run()
    for i in range(10):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/1000")
    r.line(T0 + 200, "PROGRESS 5/500")
    assert r.s["setbacks"][-1]["kind"] == "new-setup"
    assert r.s["peak"] == 5


def test_requeue_and_platform_retry():
    r = Run()
    r.tick("Running", T0 + 1, attempt=1)
    r.line(T0 + 10, "PROGRESS 50/100")
    r.tick("Pending", T0 + 20, attempt=2)
    assert r.kinds()[-2:] == ["retry", "requeued"]
    r.tick("Running", T0 + 60, attempt=2)
    r.line(T0 + 80, "PROGRESS 40/100")
    assert r.s["setbacks"][-1]["kind"] == "resume"
    assert r.s["setbacks"][-1]["lost_s"] == pytest.approx(70.0)


@pytest.mark.parametrize(
    "ticks",
    [
        [("Pending", 100, 1), ("late-line", 95, None), ("Pending", 110, 2)],
        [("Running", 100, 2), ("Pending", 110, 2)],
        [("Pending", 100, 2)],
    ],
)
def test_one_platform_retry_closes_one_attempt(ticks):
    r = Run()
    r.tick("Running", T0 + 1, attempt=1)
    r.line(T0 + 2, "PROGRESS_PHASE train")
    for i in range(9):
        r.line(T0 + 10 + 10 * i, f"PROGRESS {10 * i}/100")
    for status, t, attempt in ticks:
        if status == "late-line":
            r.line(T0 + t, "RuntimeError: CUDA error: an illegal memory access")
        else:
            r.tick(status, T0 + t, attempt=attempt)
    r.tick("Running", T0 + 130, attempt=2)
    r.line(T0 + 140, "PROGRESS_PHASE train")
    r.line(T0 + 150, "PROGRESS 40/100")
    assert r.s["attempt_no"] == 2
    assert r.s["peak"] == 80
    assert [b["kind"] for b in r.s["setbacks"]] == ["resume"]


def test_retries_seen_only_as_new_attempt_numbers_all_count():
    r = Run()
    r.tick("Running", T0 + 1, attempt=1)
    for n, t in enumerate((2, 30, 60), start=1):
        if n > 1:
            r.tick("Running", T0 + t - 10, attempt=n)
        r.line(T0 + t, "PROGRESS_PHASE train")
        r.line(T0 + t + 8, f"PROGRESS {60 - 10 * n}/100")
    assert r.s["attempt_no"] == 3
    assert [st["attempt"] for st in r.s["stages"]] == [1, 2, 3]
    assert len(r.s["setbacks"]) == 2


def test_tqdm_epoch_rollover_is_not_a_setback():
    r = Run()
    for ep in range(3):
        for i in range(0, 101, 20):
            r.line(T0 + ep * 100 + i, f"Epoch {ep}: {i}%|███| {i}/100 [00:01<00:01]")
    assert r.s["setbacks"] == []
    r.line(T0 + 400, "Epoch 1: 60%|███| 60/100 [00:01<00:01]")
    assert r.s["setbacks"][-1]["kind"] == "resume"


def test_progress_lines_outrank_tqdm():
    r = Run()
    r.line(T0 + 1, " 90%|█████████ | 9/10 [00:01<00:00]")
    r.line(T0 + 2, "PROGRESS 100/1000")
    r.line(T0 + 3, " 10%|█         | 1/10 [00:01<00:00]")
    assert (r.s["step"], r.s["source"], r.s["setbacks"]) == (100, "progress", [])


def test_a_new_tqdm_bar_in_the_same_attempt_is_not_a_setback():
    r = Run()
    r.line(T0 + 1, "PROGRESS_PHASE eval")
    for shots in range(2):  # lm-eval: one bar for 0-shot, then a new one for 5-shot
        for i in range(0, 1320, 330):
            r.line(T0 + 100 * shots + i / 10, f"Processed prompts: {i * 100 // 1319}%|█| {i}/1319")
    assert r.s["setbacks"] == []
    assert r.s["peak"] == r.s["step"]


def test_a_tqdm_drop_after_a_relaunch_is_a_setback():
    r = Run()
    for i in range(0, 60, 10):
        r.line(T0 + i, f"{i}%|█| {i}/100")
    tracker.end_attempt(r.s, T0 + 70)
    r.line(T0 + 200, " 30%|█| 30/100")
    assert r.s["setbacks"][-1]["kind"] == "resume"


# -- stages --------------------------------------------------------------------------------


def test_stages_keep_their_own_bars_and_quiet_stages_do_not_stall():
    r = Run()
    r.line(T0 + 1, "PROGRESS_PHASE setup")
    r.line(T0 + 60, "PROGRESS_PHASE train")
    for i in range(11):
        r.line(T0 + 60 + 10 * i, f"PROGRESS {10 * i}/100")
    r.line(T0 + 175, "PROGRESS_PHASE eval")
    assert r.s["step"] is None
    r.tick("Running", T0 + 175 + 900)  # 15 quiet minutes of eval: not a stall
    assert "stall" not in r.kinds()
    stages = [e["msg"] for e in r.events if e["kind"] == "stage"]
    assert stages[-1] == "train-42: stage eval (train took 1m55s)"
    done = tracker.finish(r.s, "done", T0 + 1200)
    assert "setup 59s, train 1m55s, eval 17m05s" in done["msg"]


def test_relaunch_that_trains_again_is_compared_with_old_training():
    r = Run()
    r.line(T0 + 1, "PROGRESS_PHASE train")
    for i in range(6):
        r.line(T0 + 10 * i, f"PROGRESS {10 * i}/100")
    r.line(T0 + 60, "RuntimeError: NCCL timeout")
    tracker.end_attempt(r.s, T0 + 70)
    r.line(T0 + 100, "PROGRESS_PHASE setup")
    r.line(T0 + 150, "PROGRESS_PHASE train")
    r.line(T0 + 160, "PROGRESS 30/100")
    assert r.s["setbacks"][-1]["kind"] == "resume"
    assert "NCCL timeout" in r.s["setbacks"][-1]["cause"]
    assert r.s["peak"] == 50


def test_stages_after_the_broken_one_start_fresh():
    r = Run()
    for attempt in range(3):
        base = T0 + 1000 * attempt
        r.line(base + 1, "PROGRESS_PHASE train")
        r.line(base + 2, "PROGRESS 100/100")
        r.line(base + 3, "PROGRESS_PHASE eval")
        r.line(base + 4, "PROGRESS 13/1319")
        r.line(base + 5, "ValueError: bad checkpoint")
        tracker.end_attempt(r.s, base + 10)
        tracker.open_attempt(r.s)
    r.line(T0 + 3001, "PROGRESS_PHASE train")
    r.line(T0 + 3002, "PROGRESS 100/100")
    r.line(T0 + 3003, "PROGRESS_PHASE eval")
    r.line(T0 + 3004, "PROGRESS 0/1319")
    assert [(b["kind"], b["from"], b["to"]) for b in r.s["setbacks"]] == [("restart", 13, 0)]
    r.tick("Running", T0 + 3005)
    assert r.s["last_error"] is None


def test_done_summary():
    r = Run()
    r.line(T0 + 10, "PROGRESS 500/1000")
    r.line(T0 + 20, "PROGRESS 400/1000")
    r.s["cost"] = 1.234
    e = tracker.finish(r.s, "done", T0 + 3600)
    assert e["kind"] == "done"
    assert "done in 1h00m" in e["msg"]
    assert "1 setback(s)" in e["msg"]
    assert "$1.23" in e["msg"]


# -- server labels -------------------------------------------------------------------------


def progress_label(**fields):
    return {tracker.PROGRESS_LABEL: json.dumps(fields)}


def test_progress_label_is_used_instead_of_the_text():
    r = Run()
    r.entry(T0 + 1, "step done", progress_label(step=40, total=100, source="progress", attempt=2))
    assert (r.s["step"], r.s["total"], r.s["source"], r.s["attempt"]) == (40, 100, "progress", 2)


def test_tqdm_label_keeps_its_epoch_and_progress_outranks_it():
    r = Run()
    r.entry(T0 + 1, "bar", progress_label(step=12, total=100, source="tqdm", epoch=3))
    assert (r.s["step"], r.s["epoch"], r.s["source"]) == (12, 3, "tqdm")
    r.entry(T0 + 2, "PROGRESS 5/10", progress_label(step=5, total=10, source="progress"))
    r.entry(T0 + 3, "bar", progress_label(step=90, total=100, source="tqdm"))
    assert (r.s["step"], r.s["source"]) == (5, "progress")


def test_phase_label_starts_a_stage():
    r = Run()
    r.entry(T0 + 1, "PROGRESS_PHASE train 2/3", {tracker.PHASE_LABEL: '{"name":"train","index":2,"count":3}'})
    assert (r.s["stage"], r.s["stage_index"], r.s["stage_count"]) == ("train", 2, 3)
    assert r.kinds()[-1] == "stage"


@pytest.mark.parametrize(
    "labels",
    [
        {tracker.PROGRESS_LABEL: "not json"},
        {tracker.PROGRESS_LABEL: '{"step":1,"total":0,"source":"progress"}'},
        {tracker.PROGRESS_LABEL: '{"step":1,"total":10,"source":"other"}'},
        {"unrelated": "x"},
        None,
    ],
)
def test_a_bad_or_missing_label_falls_back_to_the_text(labels):
    r = Run()
    r.entry(T0 + 1, "PROGRESS 7/70", labels)
    assert (r.s["step"], r.s["total"]) == (7, 70)
