from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.api.logs_api import LogEntry
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
    job.is_multi_machine = False
    job.iter_log_entries.return_value = [LogEntry(message="hello from the job"), LogEntry(message="42")]
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ) as resolve_job:
        result = CliRunner().invoke(logs_job, ["my-job", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_job.assert_called_once_with("my-job", teamspace)
    assert "hello from the job" in result.output
    assert "42" in result.output
    job.iter_log_entries.assert_called_once_with(
        follow=False, tail=None, rank=None, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_follows_with_options() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    job = MagicMock()
    job.is_multi_machine = False
    job.iter_log_entries.return_value = [LogEntry(message="line 1"), LogEntry(message="line 2")]
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(
            logs_job,
            ["my-job", "--follow", "--tail", "10", "--timestamps"],
        )

    assert result.exit_code == 0
    assert result.output == "line 1\nline 2\n"
    job.iter_log_entries.assert_called_once_with(
        follow=True, tail=10, rank=None, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_selects_mmt_rank() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    mmt = MagicMock(spec=MMT)
    mmt.is_multi_machine = True
    mmt.iter_log_entries.return_value = [LogEntry(message="rank one")]
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job",
        return_value=mmt,
    ):
        result = CliRunner().invoke(logs_job, ["distributed", "--rank", "1"])

    assert result.exit_code == 0
    assert "rank one" in result.output
    mmt.iter_log_entries.assert_called_once_with(
        follow=False, tail=None, rank=1, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_rejects_rank_on_single_job() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    job = MagicMock()
    job.is_multi_machine = False
    job.iter_log_entries.side_effect = ValueError("`rank` is only supported for multi-machine jobs.")
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job",
        return_value=job,
    ):
        result = CliRunner().invoke(logs_job, ["my-job", "--rank", "1"])

    assert result.exit_code != 0
    assert "`rank` is only supported for multi-machine jobs" in result.output
    job.iter_log_entries.assert_called_once_with(
        follow=False, tail=None, rank=1, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_merges_mmt_without_rank() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    mmt = MagicMock(spec=MMT)
    mmt.is_multi_machine = True
    machine0 = MagicMock()
    machine0.resource_id = "job-0"
    machine0.name = "distributed-0"
    machine1 = MagicMock()
    machine1.resource_id = "job-1"
    machine1.name = "distributed-1"
    mmt.machines = (machine0, machine1)
    mmt.iter_log_entries.return_value = [
        LogEntry(message="zero", resource_id="job-0"),
        LogEntry(message="one", resource_id="job-1"),
    ]
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job",
        return_value=mmt,
    ):
        result = CliRunner().invoke(logs_job, ["distributed"])

    assert result.exit_code == 0
    assert "[distributed-0] zero" in result.output
    assert "[distributed-1] one" in result.output
    mmt.iter_log_entries.assert_called_once_with(
        follow=False, tail=None, rank=None, since=None, until=None, query=None, severity=None
    )


@mock_command_logging
def test_job_logs_passes_filters() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    teamspace = MagicMock()
    job = MagicMock()
    job.is_multi_machine = False
    job.iter_log_entries.return_value = [LogEntry(message="boom")]
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(logs_job, ["my-job", "--query", "boom", "--severity", "error"])

    assert result.exit_code == 0, result.output
    job.iter_log_entries.assert_called_once_with(
        follow=False, tail=None, rank=None, since=None, until=None, query="boom", severity="error"
    )


@mock_command_logging
def test_job_logs_json_emits_array() -> None:
    from lightning_sdk.cli.job.logs import logs_job

    job = MagicMock()
    job.is_multi_machine = False
    job.iter_log_entries.return_value = [LogEntry(message="hello", severity="info")]
    with patch("lightning_sdk.cli.job.logs.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.job.logs.resolve_job", return_value=job
    ):
        result = CliRunner().invoke(logs_job, ["my-job", "--json"])

    assert result.exit_code == 0, result.output
    assert '"message": "hello"' in result.output
    job.iter_log_entries.assert_called_once()


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
    job.is_multi_machine = False
    job.iter_log_entries.side_effect = RuntimeError("Logs are not available while the job is Pending.")
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
