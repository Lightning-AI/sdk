from tests.cli.help import assert_help_contains


def test_mmt_inspect_help() -> None:
    assert_help_contains(
        "lightning mmt inspect --help",
        "Usage: lightning mmt inspect",
        "Inspect a multi-machine job for further details as JSON.",
    )


def test_mmts_inspect_help() -> None:
    assert_help_contains(
        "lightning mmts inspect --help",
        "Usage: lightning mmts inspect",
        "Inspect a multi-machine job for further details as JSON.",
    )


def test_inspect_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning inspect mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt inspect` instead of `lightning inspect mmt`.",
        "Usage: lightning inspect mmt [OPTIONS]",
    )
