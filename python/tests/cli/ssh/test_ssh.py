from tests.cli.help import assert_help_contains


def test_ssh_help() -> None:
    assert_help_contains("lightning ssh --help", "Usage: lightning ssh", "Configure SSH access to Studios.")
