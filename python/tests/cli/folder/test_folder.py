from tests.cli.help import assert_help_contains


def test_folder_help() -> None:
    assert_help_contains("lightning folder --help", "Usage: lightning folder", "Upload and download folders.")


def test_folders_help() -> None:
    assert_help_contains("lightning folders --help", "Usage: lightning folders", "Upload and download folders.")
