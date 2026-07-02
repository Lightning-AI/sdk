from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_help() -> None:
    assert_help_contains("lightning job --help", "Usage: lightning job", "Run batch jobs and sweeps.")


@mock_command_logging
def test_jobs_help() -> None:
    assert_help_contains("lightning jobs --help", "Usage: lightning jobs", "Run batch jobs and sweeps.")
