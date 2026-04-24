from tests.cli.help import assert_help_contains


def test_mmt_list_help() -> None:
    assert_help_contains(
        "lightning mmt list --help", "Usage: lightning mmt list", "List multi-machine jobs for a given teamspace."
    )


def test_mmts_list_help() -> None:
    assert_help_contains(
        "lightning mmts list --help", "Usage: lightning mmts list", "List multi-machine jobs for a given teamspace."
    )


def test_list_mmts_legacy_help() -> None:
    assert_help_contains(
        "lightning list mmts --help",
        "Deprecation warning:",
        "Use `lightning mmt list` instead of `lightning list mmts`.",
        "Usage: lightning list mmts [OPTIONS]",
    )
