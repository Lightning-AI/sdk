from tests.cli.help import assert_help_contains


def test_job_help() -> None:
    assert_help_contains("lightning job --help", "Usage: lightning job", "Manage Lightning AI Jobs.")


def test_jobs_help() -> None:
    assert_help_contains("lightning jobs --help", "Usage: lightning jobs", "Manage Lightning AI Jobs.")
