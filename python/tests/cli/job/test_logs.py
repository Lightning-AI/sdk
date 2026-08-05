from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.mmt import MMT
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_logs_help() -> None:
    assert_help_contains(
        "lightning job logs --help",
        "Usage: lightning job logs",
        "Print the logs for a job.",
        "--follow",
        "--tail",
        "--rank",
        "--timestamps",
        "configured default teamspace",
        "--query",
        "--severity",
    )


@mock_command_logging
def test_jobs_logs_help() -> None:
    assert_help_contains(
        "lightning jobs logs --help",
        "Usage: lightning jobs logs",
        "Print the logs for a job.",
    )


@mock_command_logging
def test_job_logs_help_shows_positional_name() -> None:
    assert_help_contains("lightning job logs --help", "Usage: lightning job logs [OPTIONS] [NAME]")


@mock_command_logging
def test_job_logs_prints_snapshot() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    job = MagicMock()
    job.logs.return_value = "hello from the job\n42"
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ) as resolve_job:
        result = CliRunner().invoke(logs_job, ["my-job", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_job.assert_called_once_with("my-job", teamspace)
    assert "hello from the job" in result.output
    assert "42" in result.output
    job.logs.assert_called_once_with(
        follow=False, tail=None, rank=None, timestamps=False, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_follows_with_options() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    job = MagicMock()
    job.logs.return_value = iter(["line 1", "line 2"])
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(
            logs_job,
            ["my-job", "--follow", "--tail", "10", "--rank", "2", "--timestamps"],
        )

    assert result.exit_code == 0
    assert result.output == "line 1\nline 2\n"
    job.logs.assert_called_once_with(
        follow=True, tail=10, rank=2, timestamps=True, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_selects_mmt_rank() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    mmt = MagicMock(spec=MMT)
    mmt.is_multi_machine = True
    machine = MagicMock()
    machine.logs.return_value = "rank one"
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job",
        return_value=mmt,
    ), patch(
        "lightning_sdk.cli.job.logs.resolve_job_machine",
        return_value=machine,
    ) as resolve_rank:
        result = CliRunner().invoke(logs_job, ["distributed", "--rank", "1"])

    assert result.exit_code == 0
    assert "rank one" in result.output
    resolve_rank.assert_called_once_with(mmt, 1)
    machine.logs.assert_called_once_with(
        follow=False, tail=None, rank=0, timestamps=False, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_merges_mmt_without_rank() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    mmt = MagicMock(spec=MMT)
    mmt.is_multi_machine = True
    mmt.logs.return_value = "[distributed-0] zero\n[distributed-1] one"
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job",
        return_value=mmt,
    ):
        result = CliRunner().invoke(logs_job, ["distributed"])

    assert result.exit_code == 0
    assert "distributed-0" in result.output
    assert "distributed-1" in result.output
    mmt.logs.assert_called_once_with(
        follow=False, tail=None, timestamps=False, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_passes_filters() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    job = MagicMock()
    job.logs.return_value = "boom"
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(logs_job, ["my-job", "--query", "boom", "--severity", "error"])

    assert result.exit_code == 0, result.output
    job.logs.assert_called_once_with(
        follow=False, tail=None, rank=None, timestamps=False, since=None, until=None, query="boom", severity="error"
    )


@mock_command_logging
def test_job_logs_rejects_unknown_severity() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    with patch("lightning_sdk.cli.job.logs.resolve_job") as resolve_job:
        result = CliRunner().invoke(logs_job, ["my-job", "--severity", "critical"])

    assert result.exit_code != 0
    resolve_job.assert_not_called()


@mock_command_logging
def test_job_logs_reports_sdk_errors_cleanly() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    job = MagicMock()
    job.logs.side_effect = RuntimeError("Logs are not available while the job is Pending.")
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(logs_job, ["my-job"])

    assert result.exit_code != 0
    assert "Pending" in result.output
    assert not isinstance(result.exception, RuntimeError)


@mock_command_logging
def test_job_logs_requires_name_without_listing_resources() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.utils.resource_resolution.Job"
    ) as job:
        result = CliRunner().invoke(logs_job)

    assert result.exit_code != 0
    assert "Missing job name. Pass JOB." in result.output
    job.assert_not_called()
    assert teamspace.mock_calls == []


def _invoke_tui(argv: list) -> MagicMock:
    from lightning_sdk.cli.job.logs import logs_job

    job = MagicMock()
    job.resource_id = "job-1"
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ), patch("lightning_sdk.cli.logs_tui.run_tui") as run_tui:
        result = CliRunner().invoke(logs_job, ["my-job", "--tui", *argv])

    assert result.exit_code == 0, result.output
    run_tui.assert_called_once()
    return run_tui


@mock_command_logging
def test_job_logs_tui_defaults_to_live() -> None:
    assert _invoke_tui([]).call_args.kwargs["follow"] is True


@mock_command_logging
def test_job_logs_tui_since_starts_paused() -> None:
    assert _invoke_tui(["--since", "2h"]).call_args.kwargs["follow"] is False


@mock_command_logging
def test_job_logs_tui_until_starts_paused() -> None:
    assert _invoke_tui(["--until", "30m"]).call_args.kwargs["follow"] is False


@mock_command_logging
def test_job_logs_tui_follow_flag_overrides_since() -> None:
    assert _invoke_tui(["--since", "2h", "--follow"]).call_args.kwargs["follow"] is True
