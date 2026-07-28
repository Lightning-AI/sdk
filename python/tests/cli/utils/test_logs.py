from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import rich_click as click
from click.testing import CliRunner

from lightning_sdk.api.logs_api import LogEntry
from lightning_sdk.cli.utils.logs import (
    LIVE_FALLBACK_IDLE_TIMEOUT,
    LogSelection,
    deployment_replica_labels,
    highlight,
    read_logs,
    resolve_time,
)


def test_resolve_time_accepts_durations() -> None:
    resolved = resolve_time("2h", "--since")

    # the server only parses RFC3339 and silently ignores anything else, so durations are
    # resolved before the request goes out
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(resolved)
    assert 1.9 * 3600 < delta.total_seconds() < 2.1 * 3600
    for value, unit_seconds in (("30s", 30), ("5m", 300), ("3d", 3 * 86400), ("1w", 7 * 86400)):
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(resolve_time(value, "--since"))
        assert unit_seconds * 0.95 < delta.total_seconds() < unit_seconds * 1.05 + 1


def test_resolve_time_passes_rfc3339_through_and_assumes_utc() -> None:
    assert resolve_time("2026-07-27T00:00:00Z", "--since") == "2026-07-27T00:00:00+00:00"
    assert resolve_time("2026-07-27T00:00:00+02:00", "--since") == "2026-07-27T00:00:00+02:00"
    # a bare timestamp is not valid RFC3339 without an offset, so it is read as UTC
    assert resolve_time("2026-07-27T00:00:00", "--since") == "2026-07-27T00:00:00+00:00"
    assert resolve_time(None, "--since") is None


def test_resolve_time_rejects_anything_else() -> None:
    with pytest.raises(click.UsageError, match="duration like 30s/5m/2h/3d/1w"):
        resolve_time("last tuesday", "--since")


def test_highlight_marks_case_insensitive_matches() -> None:
    assert (
        highlight("connection ERROR here", "error")
        == f"connection {click.style('ERROR', fg=(167, 139, 250), bold=True)} here"
    )
    assert highlight("plain", None) == "plain"


def _patch_api(monkeypatch, entries):
    stream = MagicMock(return_value=list(entries))
    monkeypatch.setattr(
        "lightning_sdk.cli.utils.logs.LogsApi",
        MagicMock(return_value=SimpleNamespace(stream=stream)),
    )
    return stream


def _run(fn):
    """Invoke ``fn`` through a click command so click.echo output is captured."""

    @click.command()
    def _cmd() -> None:
        fn()

    return CliRunner().invoke(_cmd)


def test_read_logs_labels_lines_by_resource(monkeypatch) -> None:
    _patch_api(
        monkeypatch,
        [LogEntry(message="ready", resource_id="job-0"), LogEntry(message="serving", resource_id="job-1")],
    )
    selection = LogSelection(
        teamspace_id="ts-id",
        deployment_id="dep-id",
        labels={"job-0": "replica-0", "job-1": "replica-1"},
    )

    result = _run(lambda: read_logs(selection))

    assert result.exit_code == 0, result.output
    assert result.output == "[replica-0] ready\n[replica-1] serving\n"


def test_read_logs_leaves_single_resource_output_unlabelled(monkeypatch) -> None:
    _patch_api(monkeypatch, [LogEntry(message="ready", resource_id="job-0")])
    selection = LogSelection(teamspace_id="ts-id", job_ids=["job-0"])

    result = _run(lambda: read_logs(selection))

    assert result.output == "ready\n"


def test_read_logs_passes_filters_and_stream_mode(monkeypatch) -> None:
    stream = _patch_api(monkeypatch, [])
    selection = LogSelection(teamspace_id="ts-id", mmt_id="mmt-1")

    result = _run(
        lambda: read_logs(selection, query="boom", severity="error", tail=25, since="2026-07-27T00:00:00+00:00")
    )

    assert result.exit_code == 0, result.output
    kwargs = stream.call_args.kwargs
    assert kwargs["mmt_id"] == "mmt-1"
    assert kwargs["query"] == "boom"
    assert kwargs["severity"] == "error"
    assert kwargs["tail"] == 25
    assert kwargs["since"] == "2026-07-27T00:00:00+00:00"
    assert kwargs["follow"] is False
    # a resource with nothing saved still shows its live stream, bounded by the idle timeout
    assert kwargs["fallback_to_live"] is True
    assert kwargs["idle_timeout"] == LIVE_FALLBACK_IDLE_TIMEOUT
    assert "No logs matched." in result.output


def test_read_logs_follow_tails_without_an_idle_timeout(monkeypatch) -> None:
    stream = _patch_api(monkeypatch, [LogEntry(message="live")])
    selection = LogSelection(teamspace_id="ts-id", job_ids=["job-0"])

    result = _run(lambda: read_logs(selection, follow=True))

    assert result.output == "live\n"
    kwargs = stream.call_args.kwargs
    assert kwargs["follow"] is True
    assert kwargs["idle_timeout"] is None
    assert kwargs["fallback_to_live"] is False


def test_read_logs_highlights_matches(monkeypatch) -> None:
    _patch_api(monkeypatch, [LogEntry(message="connection ERROR here")])
    selection = LogSelection(teamspace_id="ts-id", job_ids=["job-0"])

    @click.command()
    def _cmd() -> None:
        read_logs(selection, query="error")

    result = CliRunner().invoke(_cmd, color=True)

    assert click.style("ERROR", fg=(167, 139, 250), bold=True) in result.output


def test_read_logs_reports_a_missing_websocket_client_cleanly(monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("Following logs requires the 'websocket-client' package")

    monkeypatch.setattr(
        "lightning_sdk.cli.utils.logs.LogsApi",
        MagicMock(return_value=SimpleNamespace(stream=_boom)),
    )
    selection = LogSelection(teamspace_id="ts-id", job_ids=["job-0"])

    result = _run(lambda: read_logs(selection, follow=True))

    assert result.exit_code == 1
    assert not isinstance(result.exception, RuntimeError)


def test_deployment_replica_labels_only_labels_when_several_replicas(monkeypatch) -> None:
    api = MagicMock()
    api.list_deployment_jobs.return_value = [
        SimpleNamespace(id="job-0", name="replica-0"),
        SimpleNamespace(id="job-1", name="replica-1"),
    ]
    monkeypatch.setattr("lightning_sdk.api.deployment_api.DeploymentApi", lambda: api)
    assert deployment_replica_labels("ts-id", "dep-id") == {"job-0": "replica-0", "job-1": "replica-1"}

    api.list_deployment_jobs.return_value = [SimpleNamespace(id="job-0", name="replica-0")]
    assert deployment_replica_labels("ts-id", "dep-id") == {}
