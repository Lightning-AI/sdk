from tests.cli.help import assert_help_contains


def test_folder_help() -> None:
    assert_help_contains("lightning folder --help", "Usage: lightning folder", "Manage folder transfers.")


def test_folders_help() -> None:
    assert_help_contains("lightning folders --help", "Usage: lightning folders", "Manage folder transfers.")
