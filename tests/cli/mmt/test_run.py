from tests.cli.help import assert_help_contains


def test_mmt_run_help() -> None:
    assert_help_contains(
        "lightning mmt run --help",
        "Usage: lightning mmt run",
        "Run async workloads on multiple machines using a docker image.",
    )


def test_mmts_run_help() -> None:
    assert_help_contains(
        "lightning mmts run --help",
        "Usage: lightning mmts run",
        "Run async workloads on multiple machines using a docker image.",
    )


def test_run_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning run mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt run` instead of `lightning run mmt`.",
        "Usage: lightning run mmt [OPTIONS]",
    )
