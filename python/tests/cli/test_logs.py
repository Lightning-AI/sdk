import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional, Sequence
from unittest.mock import MagicMock

from click.testing import CliRunner

from lightning_sdk.api.logs_api import LogEntry, LogsPage
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_logs_help() -> None:
    assert_help_contains(
        "lightning logs --help",
        "Usage: lightning logs",
        "Search and page through a teamspace's logs.",
        "lightning job logs my-job",
        "--tail",
        "--follow",
        "--limit",
        "--json",
    )


def _entry(message: str, severity: str = "info", ts: bool = True, resource_id: str = "job-123") -> LogEntry:
    return LogEntry(
        timestamp=datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc) if ts else None,
        message=message,
        severity=severity,
        resource_id=resource_id,
        line=1,
    )


def _page(entries: Sequence[LogEntry] = (), next_page_token: Optional[str] = None, follow_url: Optional[str] = None):
    return LogsPage(entries=list(entries), next_page_token=next_page_token, follow_url=follow_url)


def _patch(
    monkeypatch,
    page: LogsPage,
    captured: dict,
    job: Optional[object] = None,
    mmt: Optional[object] = None,
    stream: Sequence[LogEntry] = (),
) -> None:
    class _FakeAction:
        def __call__(self, teamspace=None):
            captured["teamspace"] = teamspace
            return SimpleNamespace(id="ts-id", name="org/teamspace")

        def _resolve_job(self, name, teamspace=None):
            captured["job_name"] = name
            return job

        def _resolve_mmt(self, name, teamspace=None):
            captured["mmt_name"] = name
            return mmt

    api = MagicMock()
    api.get_page.return_value = page
    api.stream.return_value = list(stream)
    captured["api"] = api

    monkeypatch.setattr("lightning_sdk.cli.legacy.job_and_mmt_action._JobAndMMTAction", _FakeAction)
    monkeypatch.setattr("lightning_sdk.cli.logs.LogsApi", lambda: api)


@mock_command_logging
def test_logs_prints_entries_and_next_page_token(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page([_entry("hello"), _entry("world")], next_page_token="tok-2"), captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--job-id", "job-123"])

    assert result.exit_code == 0, result.output
    assert "hello" in result.output
    assert "world" in result.output
    assert "2026-07-24T12:00:00" in result.output
    assert "Next page — run:" in result.output
    assert "--page-token tok-2" in result.output
    # teamspace id is passed positionally to the logs API
    assert captured["api"].get_page.call_args.args == ("ts-id",)


@mock_command_logging
def test_logs_no_timestamps(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page([_entry("plain line")]), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--no-timestamps"])

    assert result.exit_code == 0, result.output
    assert "plain line" in result.output
    assert "2026-07-24" not in result.output


@mock_command_logging
def test_logs_passes_limit_cursor_and_severity(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(
        logs,
        [
            "--job-id",
            "job-1",
            "--query",
            "error",
            "--limit",
            "50",
            "--severity",
            "WARNING",
            "--page-token",
            "prev-tok",
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured["api"].get_page.call_args.kwargs
    assert kwargs["query"] == "error"
    assert kwargs["page_size"] == 50
    assert kwargs["severity"] == "warning"
    assert kwargs["page_token"] == "prev-tok"
    assert "No logs matched." in result.output


@mock_command_logging
def test_logs_converts_relative_since_to_a_timestamp(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--since", "2h"])

    assert result.exit_code == 0, result.output
    since = captured["api"].get_page.call_args.kwargs["since"]
    # the server only parses RFC3339 and silently ignores anything else, so "2h" is resolved here
    parsed = datetime.fromisoformat(since)
    delta = datetime.now(timezone.utc) - parsed
    assert 1.9 * 3600 < delta.total_seconds() < 2.1 * 3600


@mock_command_logging
def test_logs_rejects_an_unparseable_since(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--since", "last tuesday"])

    assert result.exit_code == 2
    captured["api"].get_page.assert_not_called()


@mock_command_logging
def test_logs_highlights_query_matches_on_terminal(monkeypatch) -> None:
    import rich_click as click

    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page([_entry("connection ERROR here")]), captured)

    # color=True keeps ANSI (simulates a terminal); match highlight is case-insensitive.
    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--query", "error"], color=True)

    assert result.exit_code == 0, result.output
    assert click.style("ERROR", fg=(167, 139, 250), bold=True) in result.output


@mock_command_logging
def test_logs_no_highlight_when_piped(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page([_entry("connection ERROR here")]), captured)

    # default color=False simulates a pipe: ANSI must be stripped, text stays plain.
    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--query", "error"])

    assert result.exit_code == 0, result.output
    assert "connection ERROR here" in result.output
    assert "\x1b[" not in result.output


@mock_command_logging
def test_logs_job_ids_passed_directly(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-raw", "--job-id", "job-raw-2"])

    assert result.exit_code == 0, result.output
    assert "job_name" not in captured  # no name resolution
    assert captured["api"].get_page.call_args.kwargs["job_ids"] == ["job-raw", "job-raw-2"]


@mock_command_logging
def test_logs_resolves_job_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured, job=SimpleNamespace(resource_id="job-abc"))

    result = CliRunner().invoke(logs, ["--job-name", "my-job"])

    assert result.exit_code == 0, result.output
    assert captured["job_name"] == "my-job"
    assert captured["api"].get_page.call_args.kwargs["job_ids"] == ["job-abc"]


@mock_command_logging
def test_logs_resolves_mmt_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured, mmt=SimpleNamespace(resource_id="mmt-abc"))
    monkeypatch.setattr("lightning_sdk.cli.logs._mmt_machine_labels", lambda *a, **k: {})

    result = CliRunner().invoke(logs, ["--mmt-name", "my-mmt"])

    assert result.exit_code == 0, result.output
    assert captured["mmt_name"] == "my-mmt"
    assert captured["api"].get_page.call_args.kwargs["mmt_id"] == "mmt-abc"


@mock_command_logging
def test_logs_resolves_deployment_name_and_labels_replicas(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page([_entry("from a replica", resource_id="job-1")]), captured)

    dep_api = MagicMock()
    dep_api.get_deployment_by_name.return_value = SimpleNamespace(id="dpl-abc")
    monkeypatch.setattr("lightning_sdk.api.deployment_api.DeploymentApi", lambda: dep_api)
    monkeypatch.setattr("lightning_sdk.cli.logs.deployment_replica_labels", lambda *a: {"job-1": "replica-0"})

    result = CliRunner().invoke(logs, ["--deployment-name", "my-api"])

    assert result.exit_code == 0, result.output
    dep_api.get_deployment_by_name.assert_called_once_with("my-api", "ts-id")
    assert captured["api"].get_page.call_args.kwargs["deployment_id"] == "dpl-abc"
    # a merged read marks which replica each line came from
    assert "[replica-0] from a replica" in result.output


@mock_command_logging
def test_logs_resolves_sandbox_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli import logs as logs_module
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    monkeypatch.setattr(logs_module, "_resolve_sandbox_id", lambda name, ts: f"sbx-for-{name}")

    result = CliRunner().invoke(logs, ["--sandbox-name", "devbox"])

    assert result.exit_code == 0, result.output
    assert captured["api"].get_page.call_args.kwargs["sandbox_id"] == "sbx-for-devbox"


@mock_command_logging
def test_logs_sandbox_name_scoped_key_error_is_actionable(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    class _FakeSandbox:
        def list(self, **kwargs):
            raise RuntimeError("Use a teamspace- or org-scoped API key, not your personal login key.")

    monkeypatch.setattr("lightning_sdk.sandbox.sandbox.Sandbox", lambda *a, **k: _FakeSandbox())

    result = CliRunner().invoke(logs, ["--sandbox-name", "devbox"])

    # ClickException (exit 1), not an unhandled RuntimeError, and never reaches the logs API.
    assert result.exit_code == 1
    assert not isinstance(result.exception, RuntimeError)
    captured["api"].get_page.assert_not_called()


@mock_command_logging
def test_logs_sandbox_command_id_passthrough(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--sandbox-id", "sbx-1", "--sandbox-command-id", "cmd-1"])

    assert result.exit_code == 0, result.output
    kwargs = captured["api"].get_page.call_args.kwargs
    assert kwargs["sandbox_id"] == "sbx-1"
    assert kwargs["sandbox_command_ids"] == ["cmd-1"]


@mock_command_logging
def test_logs_rejects_id_and_name_together(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--job-name", "my-job"])

    # rich_click renders usage errors on its own console, so assert on the exit code
    # and that the guard rejected the call before it reached the API.
    assert result.exit_code == 2
    captured["api"].get_page.assert_not_called()


@mock_command_logging
def test_logs_requires_a_resource(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--query", "boom"])

    # the endpoint rejects a read with no resource; catch it here with a usable message instead
    assert result.exit_code == 2
    captured["api"].get_page.assert_not_called()


@mock_command_logging
def test_logs_tail_streams_the_last_lines(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured, stream=[_entry("second to last"), _entry("last")])

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--tail", "2", "--no-timestamps"])

    assert result.exit_code == 0, result.output
    assert result.output == "second to last\nlast\n"
    captured["api"].get_page.assert_not_called()
    kwargs = captured["api"].stream.call_args.kwargs
    assert kwargs["tail"] == 2
    assert kwargs["follow"] is False
    # a resource with nothing saved still shows its live stream, bounded by the idle timeout
    assert kwargs["fallback_to_live"] is True


@mock_command_logging
def test_logs_follow_streams_live(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured, stream=[_entry("live line")])

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--follow", "--no-timestamps"])

    assert result.exit_code == 0, result.output
    assert result.output == "live line\n"
    kwargs = captured["api"].stream.call_args.kwargs
    assert kwargs["follow"] is True
    assert kwargs["idle_timeout"] is None


@mock_command_logging
def test_logs_rejects_tail_with_limit(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--tail", "5", "--limit", "5"])

    assert result.exit_code == 2
    captured["api"].stream.assert_not_called()
    captured["api"].get_page.assert_not_called()


@mock_command_logging
def test_logs_rejects_follow_with_page_token(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page(), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--follow", "--page-token", "tok"])

    assert result.exit_code == 2
    captured["api"].stream.assert_not_called()


@mock_command_logging
def test_logs_next_page_command_preserves_original_flags(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(
        monkeypatch,
        _page([_entry("x")], next_page_token="tok-next"),
        captured,
        mmt=SimpleNamespace(resource_id="mmt-abc"),
    )
    monkeypatch.setattr("lightning_sdk.cli.logs._mmt_machine_labels", lambda *a, **k: {})

    result = CliRunner().invoke(logs, ["--mmt-name", "my-mmt", "--query", "boom", "--limit", "5"])

    assert result.exit_code == 0, result.output
    # reproduces the name the user typed, not the resolved --mmt-id, and carries the new token
    assert "lightning logs --mmt-name my-mmt --query boom --limit 5 --page-token tok-next" in result.output
    assert "--mmt-id" not in result.output


@mock_command_logging
def test_logs_json_output(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    _patch(monkeypatch, _page([_entry("boom", severity="error")], next_page_token="tok-9"), captured)

    result = CliRunner().invoke(logs, ["--job-id", "job-1", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["next_page_token"] == "tok-9"
    assert payload["entries"][0]["message"] == "boom"
    assert payload["entries"][0]["severity"] == "error"
