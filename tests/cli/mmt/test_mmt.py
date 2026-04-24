from tests.cli.help import assert_help_contains


def test_mmt_help() -> None:
    assert_help_contains(
        "lightning mmt --help", "Usage: lightning mmt", "Manage Lightning AI Multi-Machine Training (MMT)."
    )


def test_mmts_help() -> None:
    assert_help_contains(
        "lightning mmts --help", "Usage: lightning mmts", "Manage Lightning AI Multi-Machine Training (MMT)."
    )
