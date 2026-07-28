from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_stop_help() -> None:
    assert_help_contains("lightning job stop --help", "Usage: lightning job stop", "Stop a job.")


@mock_command_logging
def test_jobs_stop_help() -> None:
    assert_help_contains("lightning jobs stop --help", "Usage: lightning jobs stop", "Stop a job.")


@mock_command_logging
def test_stop_help() -> None:
    text = assert_help_contains(
        "lightning stop --help",
        "`lightning stop` has moved to noun-first commands:",
        "job -> lightning job stop",
        "mmt -> lightning mmt stop",
        "studio -> lightning studio stop",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_stop_job_legacy_help() -> None:
    assert_help_contains(
        "lightning stop job --help",
        "Deprecation warning:",
        "Use `lightning job stop` instead of `lightning stop job`.",
        "Usage: lightning stop job [OPTIONS] NAME",
    )


@mock_command_logging
def test_job_stop_resolves_exact_name() -> None:
    from lightning_sdk.cli.job.stop import stop_job

    teamspace = MagicMock()
    job = MagicMock()
    job.name = "train"
    with patch("lightning_sdk.cli.job.stop.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.job.stop.resolve_job", return_value=job
    ) as resolve_job:
        result = CliRunner().invoke(stop_job, ["train", "--teamspace", "org/teamspace"])

    assert result.exit_code == 0
    resolve_teamspace.assert_called_once_with("org/teamspace")
    resolve_job.assert_called_once_with("train", teamspace)
    job.stop.assert_called_once_with()
