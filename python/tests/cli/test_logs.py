import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_logs_help() -> None:
    assert_help_contains(
        "lightning logs --help",
        "Usage: lightning logs",
        "Search and page through logs across a teamspace.",
    )


def _entry(message: str, severity: str = "info", ts: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc) if ts else None,
        message=message,
        severity=severity,
        resource_id="job-123",
        line=1,
    )


def _patch(
    monkeypatch,
    response: MagicMock,
    captured: dict,
    job: Optional[MagicMock] = None,
    mmt: Optional[MagicMock] = None,
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
    api.search_logs.return_value = response
    captured["api"] = api

    monkeypatch.setattr("lightning_sdk.cli.legacy.job_and_mmt_action._JobAndMMTAction", _FakeAction)
    monkeypatch.setattr("lightning_sdk.api.job_api.JobApiV2", lambda: api)


@mock_command_logging
def test_logs_prints_entries_and_next_page_token(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(
        entries=[_entry("hello"), _entry("world")],
        next_page_token="tok-2",
        follow_url=None,
    )
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace"])

    assert result.exit_code == 0, result.output
    assert "hello" in result.output
    assert "world" in result.output
    assert "2026-07-24T12:00:00" in result.output
    assert "Next page — run:" in result.output
    assert "lightning logs --teamspace org/teamspace --page-token tok-2" in result.output
    assert captured["api"].search_logs.call_args.kwargs["teamspace_id"] == "ts-id"


@mock_command_logging
def test_logs_no_timestamps(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[_entry("plain line")], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--no-timestamps"])

    assert result.exit_code == 0, result.output
    assert "plain line" in result.output
    assert "2026-07-24" not in result.output


@mock_command_logging
def test_logs_passes_search_limit_and_cursor(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(
        logs,
        [
            "--teamspace",
            "org/teamspace",
            "--query",
            "error",
            "--limit",
            "50",
            "--severity",
            "WARNING",
            "--page-token",
            "prev-tok",
            "--since",
            "1h",
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured["api"].search_logs.call_args.kwargs
    assert kwargs["query"] == "error"
    assert kwargs["page_size"] == 50
    assert kwargs["severity"] == "warning"
    assert kwargs["page_token"] == "prev-tok"
    assert kwargs["since"] == "1h"
    assert "No logs matched." in result.output


@mock_command_logging
def test_logs_highlights_query_matches_on_terminal(monkeypatch) -> None:
    import rich_click as click

    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[_entry("connection ERROR here")], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    # color=True keeps ANSI (simulates a terminal); match highlight is case-insensitive.
    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--query", "error"], color=True)

    assert result.exit_code == 0, result.output
    assert click.style("ERROR", fg=(167, 139, 250), bold=True) in result.output


@mock_command_logging
def test_logs_no_highlight_when_piped(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[_entry("connection ERROR here")], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    # default color=False simulates a pipe: ANSI must be stripped, text stays plain.
    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--query", "error"])

    assert result.exit_code == 0, result.output
    assert "connection ERROR here" in result.output
    assert "\x1b[" not in result.output


@mock_command_logging
def test_logs_job_id_passed_directly(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--job-id", "job-raw"])

    assert result.exit_code == 0, result.output
    assert "job_name" not in captured  # no name resolution
    assert captured["api"].search_logs.call_args.kwargs["job_ids"] == ["job-raw"]


@mock_command_logging
def test_logs_resolves_job_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    job = SimpleNamespace(resource_id="job-abc")
    _patch(monkeypatch, response, captured, job=job)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--job-name", "my-job"])

    assert result.exit_code == 0, result.output
    assert captured["job_name"] == "my-job"
    assert captured["api"].search_logs.call_args.kwargs["job_ids"] == ["job-abc"]


@mock_command_logging
def test_logs_resolves_mmt_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    mmt = SimpleNamespace(resource_id="mmt-abc")
    _patch(monkeypatch, response, captured, mmt=mmt)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--mmt-name", "my-mmt"])

    assert result.exit_code == 0, result.output
    assert captured["mmt_name"] == "my-mmt"
    assert captured["api"].search_logs.call_args.kwargs["mmt_id"] == "mmt-abc"


@mock_command_logging
def test_logs_resolves_deployment_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    dep_api = MagicMock()
    dep_api.get_deployment_by_name.return_value = SimpleNamespace(id="dpl-abc")
    monkeypatch.setattr("lightning_sdk.api.deployment_api.DeploymentApi", lambda: dep_api)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--deployment-name", "my-api"])

    assert result.exit_code == 0, result.output
    dep_api.get_deployment_by_name.assert_called_once_with("my-api", "ts-id")
    assert captured["api"].search_logs.call_args.kwargs["deployment_id"] == "dpl-abc"


@mock_command_logging
def test_logs_resolves_sandbox_name_to_id(monkeypatch) -> None:
    from lightning_sdk.cli import logs as logs_module
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    monkeypatch.setattr(logs_module, "_resolve_sandbox_id", lambda name, ts: f"sbx-for-{name}")

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--sandbox-name", "devbox"])

    assert result.exit_code == 0, result.output
    assert captured["api"].search_logs.call_args.kwargs["sandbox_id"] == "sbx-for-devbox"


@mock_command_logging
def test_logs_sandbox_name_scoped_key_error_is_actionable(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    class _FakeSandbox:
        def list(self, **kwargs):
            raise RuntimeError("Use a teamspace- or org-scoped API key, not your personal login key.")

    monkeypatch.setattr("lightning_sdk.sandbox.sandbox.Sandbox", lambda *a, **k: _FakeSandbox())

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--sandbox-name", "devbox"])

    # ClickException (exit 1), not an unhandled RuntimeError, and never reaches the logs API.
    assert result.exit_code == 1
    assert not isinstance(result.exception, RuntimeError)
    captured["api"].search_logs.assert_not_called()


@mock_command_logging
def test_logs_sandbox_command_id_passthrough(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(
        logs, ["--teamspace", "org/teamspace", "--sandbox-id", "sbx-1", "--sandbox-command-id", "cmd-1"]
    )

    assert result.exit_code == 0, result.output
    kwargs = captured["api"].search_logs.call_args.kwargs
    assert kwargs["sandbox_id"] == "sbx-1"
    assert kwargs["sandbox_command_ids"] == ["cmd-1"]


@mock_command_logging
def test_logs_rejects_id_and_name_together(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[], next_page_token=None, follow_url=None)
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--job-id", "job-1", "--job-name", "my-job"])

    # rich_click renders usage errors on its own console, so assert on the exit code
    # and that the guard rejected the call before it reached the API.
    assert result.exit_code == 2
    captured["api"].search_logs.assert_not_called()


@mock_command_logging
def test_logs_next_page_command_preserves_original_flags(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[_entry("x")], next_page_token="tok-next", follow_url=None)
    mmt = SimpleNamespace(resource_id="mmt-abc")
    _patch(monkeypatch, response, captured, mmt=mmt)

    result = CliRunner().invoke(logs, ["--mmt-name", "my-mmt", "--query", "boom", "--limit", "5"])

    assert result.exit_code == 0, result.output
    # reproduces the name the user typed, not the resolved --mmt-id, and carries the new token
    assert "lightning logs --mmt-name my-mmt --query boom --limit 5 --page-token tok-next" in result.output
    assert "--mmt-id" not in result.output


@mock_command_logging
def test_logs_json_output(monkeypatch) -> None:
    from lightning_sdk.cli.logs import logs

    captured: dict = {}
    response = SimpleNamespace(entries=[_entry("boom", severity="error")], next_page_token="tok-9", follow_url=None)
    _patch(monkeypatch, response, captured)

    result = CliRunner().invoke(logs, ["--teamspace", "org/teamspace", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["next_page_token"] == "tok-9"
    assert payload["entries"][0]["message"] == "boom"
    assert payload["entries"][0]["severity"] == "error"
