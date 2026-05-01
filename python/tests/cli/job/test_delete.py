from tests.cli.help import assert_help_contains


def test_job_delete_help() -> None:
    assert_help_contains("lightning job delete --help", "Usage: lightning job delete", "Delete a job.")


def test_jobs_delete_help() -> None:
    assert_help_contains("lightning jobs delete --help", "Usage: lightning jobs delete", "Delete a job.")


def test_delete_help() -> None:
    text = assert_help_contains(
        "lightning delete --help",
        "`lightning delete` has moved to noun-first commands:",
        "container -> lightning container delete",
        "job -> lightning job delete",
        "mmt -> lightning mmt delete",
        "studio -> lightning studio delete",
    )
    assert "Deprecation warning:" not in text


def test_delete_job_legacy_help() -> None:
    assert_help_contains(
        "lightning delete job --help",
        "Deprecation warning:",
        "Use `lightning job delete` instead of `lightning delete job`.",
        "Usage: lightning delete job [OPTIONS] NAME",
    )
