from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_job_list_help() -> None:
    assert_help_contains("lightning job list --help", "Usage: lightning job list", "List jobs for a given teamspace.")


@mock_command_logging
def test_jobs_list_help() -> None:
    assert_help_contains("lightning jobs list --help", "Usage: lightning jobs list", "List jobs for a given teamspace.")


@mock_command_logging
def test_list_jobs_legacy_help() -> None:
    assert_help_contains(
        "lightning list jobs --help",
        "Deprecation warning:",
        "Use `lightning job list` instead of `lightning list jobs`.",
        "Usage: lightning list jobs [OPTIONS]",
    )
