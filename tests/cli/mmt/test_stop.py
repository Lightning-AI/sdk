from tests.cli.help import assert_help_contains


def test_mmt_stop_help() -> None:
    assert_help_contains("lightning mmt stop --help", "Usage: lightning mmt stop", "Stop a multi-machine job.")


def test_mmts_stop_help() -> None:
    assert_help_contains("lightning mmts stop --help", "Usage: lightning mmts stop", "Stop a multi-machine job.")


def test_stop_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning stop mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt stop` instead of `lightning stop mmt`.",
        "Usage: lightning stop mmt [OPTIONS] NAME",
    )
