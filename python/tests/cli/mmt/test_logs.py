from unittest.mock import MagicMock

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_mmt_logs_help() -> None:
    assert_help_contains(
        "lightning mmt logs --help",
        "Usage: lightning mmt logs",
        "Print the logs for a multi-machine job.",
        "--follow",
        "--tail",
        "--timestamps",
        "--query",
        "--severity",
    )


@mock_command_logging
def test_mmts_logs_help() -> None:
    assert_help_contains(
        "lightning mmts logs --help",
        "Usage: lightning mmts logs",
        "Print the logs for a multi-machine job.",
    )


def _patch_action(monkeypatch, mmt: MagicMock, captured: dict) -> None:
    class _FakeJobAndMMTAction:
        def mmt(self, name=None, teamspace=None):
            captured["name"] = name
            captured["teamspace"] = teamspace
            return mmt

    monkeypatch.setattr("lightning_sdk.cli.mmt.logs._JobAndMMTAction", _FakeJobAndMMTAction)


@mock_command_logging
def test_mmt_logs_prints_merged_snapshot(monkeypatch) -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    captured: dict = {}
    mmt = MagicMock()
    mmt.logs.return_value = "[my-mmt-0] rank 0 up\n[my-mmt-1] rank 1 up"
    _patch_action(monkeypatch, mmt, captured)

    result = CliRunner().invoke(logs_mmt, ["my-mmt", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0, result.output
    assert captured == {"name": "my-mmt", "teamspace": "org/teamspace"}
    assert "[my-mmt-0] rank 0 up" in result.output
    assert "[my-mmt-1] rank 1 up" in result.output
    mmt.logs.assert_called_once_with(
        follow=False, tail=None, timestamps=False, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_mmt_logs_follows_with_options(monkeypatch) -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    captured: dict = {}
    mmt = MagicMock()
    mmt.logs.return_value = iter(["line 1", "line 2"])
    _patch_action(monkeypatch, mmt, captured)

    result = CliRunner().invoke(
        logs_mmt,
        ["my-mmt", "--follow", "--tail", "10", "--timestamps", "--query", "loss", "--severity", "error"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "line 1\nline 2\n"
    mmt.logs.assert_called_once_with(
        follow=True, tail=10, timestamps=True, since=None, until=None, query="loss", severity="error"
    )


@mock_command_logging
def test_mmt_logs_reports_sdk_errors_cleanly(monkeypatch) -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    mmt = MagicMock()
    mmt.logs.side_effect = RuntimeError("Logs are not available while the job is Pending.")
    _patch_action(monkeypatch, mmt, {})

    result = CliRunner().invoke(logs_mmt, ["my-mmt"])

    assert result.exit_code != 0
    assert "Pending" in result.output
    assert not isinstance(result.exception, RuntimeError)
