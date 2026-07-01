from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_config_help() -> None:
    assert_help_contains("lightning config --help", "Usage: lightning config", "Manage SDK and CLI settings.")
