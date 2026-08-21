from datetime import datetime, timezone
from itertools import islice
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _stream(**overrides):
    """Build a fake ``V1MetricsStream`` with the fields the class reads."""
    defaults = {
        "id": "ms-abc",
        "name": "run-42",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _metric_point(step, value, walltime):
    return SimpleNamespace(step=str(step), value=value, walltime=walltime, created_at=walltime)


def _metrics_response(points_by_metric, stream_id="ms-abc"):
    """Turn ``{"loss": [(step, value, walltime), ...]}`` into the nested response shape."""
    named = {}
    for metric_name, points in points_by_metric.items():
        ids_metrics = {stream_id: SimpleNamespace(metrics_values=[_metric_point(s, v, w) for (s, v, w) in points])}
        named[metric_name] = SimpleNamespace(ids_metrics=ids_metrics)
    return SimpleNamespace(named_metrics=named)


def _make_experiment(api):
    """Construct an ``Experiment`` with the given ``LitLoggerApi`` mock."""
    from lightning_sdk.experiment import Experiment

    teamspace = MagicMock()
    teamspace.name = "ts"
    with patch("lightning_sdk.experiment._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.experiment.LitLoggerApi", return_value=api
    ):
        return Experiment("run-42", teamspace=teamspace)


def test_experiment_resolves_stream_by_name_and_exposes_id() -> None:
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    exp = _make_experiment(api)
    assert exp.name == "run-42"
    assert exp.id == "ms-abc"


def test_experiment_raises_when_name_not_found() -> None:
    from lightning_sdk.experiment import Experiment

    teamspace = MagicMock()
    teamspace.name = "ts"
    api = MagicMock()
    api.list_metrics_streams.return_value = []
    with patch("lightning_sdk.experiment._resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.experiment.LitLoggerApi", return_value=api
    ), pytest.raises(ValueError, match="No experiment named 'missing' in teamspace 'ts'"):
        Experiment("missing", teamspace=teamspace)


def test_experiment_raises_when_teamspace_cannot_be_resolved() -> None:
    from lightning_sdk.experiment import Experiment

    with patch("lightning_sdk.experiment._resolve_teamspace", return_value=None), pytest.raises(
        ValueError, match="Cannot resolve the teamspace"
    ):
        Experiment("run-42")


def test_experiment_picks_most_recently_updated_stream_when_names_collide() -> None:
    older = _stream(id="ms-old", updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = _stream(id="ms-new", updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
    api = MagicMock()
    api.list_metrics_streams.return_value = [older, newer]
    exp = _make_experiment(api)
    assert exp.id == "ms-new"


def test_metrics_snapshot_groups_by_step() -> None:
    walltime = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.return_value = _metrics_response(
        {
            "loss": [(100, 0.31, walltime), (200, 0.28, walltime)],
            "val_acc": [(100, 0.87, walltime)],
        }
    )
    rows = _make_experiment(api).metrics()

    by_step = {row["_step"]: row for row in rows}
    assert by_step["100"]["loss"] == 0.31
    assert by_step["100"]["val_acc"] == 0.87
    assert by_step["100"]["_stream"] == "run-42"
    assert by_step["200"] == {"_step": "200", "_stream": "run-42", "_walltime": walltime, "loss": 0.28}


def test_metrics_filter_scopes_output() -> None:
    walltime = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.return_value = _metrics_response(
        {"loss": [(100, 0.31, walltime)], "val_acc": [(100, 0.87, walltime)]}
    )
    rows = _make_experiment(api).metrics(metric=["loss"])
    assert len(rows) == 1
    assert "loss" in rows[0]
    assert "val_acc" not in rows[0]


def test_metrics_tail_keeps_last_n() -> None:
    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.return_value = _metrics_response(
        {"loss": [(step, 1.0 / step, base.replace(minute=step)) for step in (1, 2, 3, 4, 5)]}
    )
    rows = _make_experiment(api).metrics(tail=2)
    assert [row["_step"] for row in rows] == ["4", "5"]


def test_metrics_since_filters_client_side() -> None:
    early = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    late = datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.return_value = _metrics_response({"loss": [(1, 0.9, early), (2, 0.5, late)]})
    rows = _make_experiment(api).metrics(since=late)
    assert [row["_step"] for row in rows] == ["2"]
    # The backend was called without walltime bounds; filtering is fully client-side.
    (call,) = api.get_logger_metrics.call_args_list
    assert "min_walltime" not in call.kwargs
    assert "max_walltime" not in call.kwargs


def test_metrics_snapshot_retries_transient_5xx() -> None:
    from lightning_sdk import experiment as experiment_module
    from lightning_sdk.lightning_cloud.openapi.rest import ApiException

    walltime = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.side_effect = [
        ApiException(status=500, reason="Internal Server Error"),
        _metrics_response({"loss": [(1, 0.5, walltime)]}),
    ]
    with patch.object(experiment_module, "_FOLLOW_POLL_INTERVAL", 0):
        rows = _make_experiment(api).metrics()
    assert len(rows) == 1
    assert rows[0]["loss"] == 0.5
    assert api.get_logger_metrics.call_count == 2


def test_metrics_follow_yields_snapshot_then_new_rows_without_replay() -> None:
    from lightning_sdk import experiment as experiment_module

    first = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    second = datetime(2026, 5, 1, 12, 1, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.side_effect = [
        _metrics_response({"loss": [(1, 0.9, first)]}),
        _metrics_response({"loss": [(1, 0.9, first), (2, 0.5, second)]}),
    ]
    with patch.object(experiment_module, "_FOLLOW_POLL_INTERVAL", 0):
        rows = list(islice(_make_experiment(api).metrics(follow=True), 2))
    assert [row["_step"] for row in rows] == ["1", "2"]


def test_metrics_follow_swallows_transient_5xx() -> None:
    from lightning_sdk import experiment as experiment_module
    from lightning_sdk.lightning_cloud.openapi.rest import ApiException

    later = datetime(2026, 5, 1, 12, 1, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.side_effect = [
        SimpleNamespace(named_metrics={}),  # empty snapshot
        ApiException(status=500, reason="Internal Server Error"),
        _metrics_response({"loss": [(1, 0.5, later)]}),
    ]
    with patch.object(experiment_module, "_FOLLOW_POLL_INTERVAL", 0):
        rows = list(islice(_make_experiment(api).metrics(follow=True), 1))
    assert [row["_step"] for row in rows] == ["1"]


def test_metrics_rejects_tail_with_follow() -> None:
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    with pytest.raises(ValueError, match="tail cannot be combined with follow"):
        _make_experiment(api).metrics(follow=True, tail=5)


def test_metrics_sorts_steps_numerically_within_a_walltime_bucket() -> None:
    walltime = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.return_value = _metrics_response(
        {"loss": [(step, 0.1, walltime) for step in (2, 10, 1, 11, 3)]}
    )
    rows = _make_experiment(api).metrics()
    assert [row["_step"] for row in rows] == ["1", "2", "3", "10", "11"]


def test_metrics_follow_yields_all_rows_sharing_a_walltime() -> None:
    # Regression for the "walltime <= cursor" cursor: if two rows share a walltime,
    # the second must still be yielded, not dropped.
    from lightning_sdk import experiment as experiment_module

    walltime = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    api = MagicMock()
    api.list_metrics_streams.return_value = [_stream()]
    api.get_logger_metrics.side_effect = [
        # Snapshot at step 1; the follow tick surfaces steps 2 and 3 at the same walltime.
        _metrics_response({"loss": [(1, 0.9, walltime)]}),
        _metrics_response({"loss": [(1, 0.9, walltime), (2, 0.8, walltime), (3, 0.7, walltime)]}),
    ]
    with patch.object(experiment_module, "_FOLLOW_POLL_INTERVAL", 0):
        rows = list(islice(_make_experiment(api).metrics(follow=True), 3))
    assert [row["_step"] for row in rows] == ["1", "2", "3"]


def test_experiment_reports_errors_to_command_history() -> None:
    from lightning_sdk.experiment import Experiment

    with patch("lightning_sdk.experiment._resolve_teamspace", return_value=None), patch(
        "lightning_sdk.utils.logging.cached_lightning_client"
    ) as fake_client:
        client = MagicMock()
        fake_client.return_value = client
        with pytest.raises(ValueError, match="Cannot resolve the teamspace"):
            Experiment("run-42")

    telemetry = client.s_dk_command_history_service_create_sdk_command_history
    telemetry.assert_called_once()
    body = telemetry.call_args.kwargs["body"]
    assert body.command == "Experiment.__init__"
    assert "ERROR" in str(body.severity)
