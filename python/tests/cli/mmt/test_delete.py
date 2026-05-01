from tests.cli.help import assert_help_contains


def test_mmt_delete_help() -> None:
    assert_help_contains("lightning mmt delete --help", "Usage: lightning mmt delete", "Delete a multi-machine job.")


def test_mmts_delete_help() -> None:
    assert_help_contains("lightning mmts delete --help", "Usage: lightning mmts delete", "Delete a multi-machine job.")


def test_delete_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning delete mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt delete` instead of `lightning delete mmt`.",
        "Usage: lightning delete mmt [OPTIONS] NAME",
    )
