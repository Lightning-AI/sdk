from unittest.mock import MagicMock, patch

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
        "configured default teamspace",
    )


@mock_command_logging
def test_mmts_logs_help() -> None:
    assert_help_contains(
        "lightning mmts logs --help",
        "Usage: lightning mmts logs",
        "Print the logs for a multi-machine job.",
    )


@mock_command_logging
def test_mmt_logs_prints_merged_snapshot() -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    teamspace = MagicMock()
    mmt = MagicMock()
    mmt.logs.return_value = "[my-mmt-0] rank 0 up\n[my-mmt-1] rank 1 up"
    with patch("lightning_sdk.cli.mmt.logs.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.mmt.logs.resolve_mmt", return_value=mmt
    ) as resolve_mmt:
        result = CliRunner().invoke(logs_mmt, ["my-mmt", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0, result.output
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_mmt.assert_called_once_with("my-mmt", teamspace)
    assert "[my-mmt-0] rank 0 up" in result.output
    assert "[my-mmt-1] rank 1 up" in result.output
    mmt.logs.assert_called_once_with(
        follow=False, tail=None, timestamps=False, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_mmt_logs_follows_with_options() -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    teamspace = MagicMock()
    mmt = MagicMock()
    mmt.logs.return_value = iter(["line 1", "line 2"])
    with patch("lightning_sdk.cli.mmt.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.mmt.logs.resolve_mmt", return_value=mmt
    ):
        result = CliRunner().invoke(
            logs_mmt,
            ["my-mmt", "--follow", "--tail", "10", "--timestamps", "--query", "loss", "--severity", "error"],
        )

    assert result.exit_code == 0, result.output
    assert "line 1\nline 2\n" in result.output
    mmt.logs.assert_called_once_with(
        follow=True, tail=10, timestamps=True, since=None, until=None, query="loss", severity="error"
    )


@mock_command_logging
def test_mmt_logs_reports_sdk_errors_cleanly() -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    teamspace = MagicMock()
    mmt = MagicMock()
    mmt.logs.side_effect = RuntimeError("Logs are not available while the job is Pending.")
    with patch("lightning_sdk.cli.mmt.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.mmt.logs.resolve_mmt", return_value=mmt
    ):
        result = CliRunner().invoke(logs_mmt, ["my-mmt"])

    assert result.exit_code != 0
    assert "Pending" in result.output
    assert not isinstance(result.exception, RuntimeError)


@mock_command_logging
def test_mmt_logs_requires_name_without_listing_resources() -> None:
    from lightning_sdk.cli.mmt.logs import logs_mmt

    teamspace = MagicMock()
    with patch("lightning_sdk.cli.mmt.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.utils.resource_resolution.MMT"
    ) as mmt:
        result = CliRunner().invoke(logs_mmt)

    assert result.exit_code != 0
    assert "Missing multi-machine job name. Pass JOB." in result.output
    mmt.assert_not_called()
    assert teamspace.mock_calls == []
