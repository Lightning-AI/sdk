from tests.cli.help import assert_help_contains


def test_job_help() -> None:
    assert_help_contains("lightning job --help", "Usage: lightning job", "Run batch jobs and sweeps.")


def test_jobs_help() -> None:
    assert_help_contains("lightning jobs --help", "Usage: lightning jobs", "Run batch jobs and sweeps.")
