from tests.cli.help import assert_help_contains


def test_mmt_help() -> None:
    assert_help_contains("lightning mmt --help", "Usage: lightning mmt", "Multi-node distributed training.")


def test_mmts_help() -> None:
    assert_help_contains("lightning mmts --help", "Usage: lightning mmts", "Multi-node distributed training.")
