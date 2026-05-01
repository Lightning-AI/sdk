from tests.cli.help import assert_help_contains


def test_file_help() -> None:
    assert_help_contains("lightning file --help", "Usage: lightning file", "Manage file transfers.")


def test_files_help() -> None:
    assert_help_contains("lightning files --help", "Usage: lightning files", "Manage file transfers.")
