from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_folder_help() -> None:
    assert_help_contains("lightning folder --help", "Usage: lightning folder", "Upload and download folders.")


@mock_command_logging
def test_folders_help() -> None:
    assert_help_contains("lightning folders --help", "Usage: lightning folders", "Upload and download folders.")
