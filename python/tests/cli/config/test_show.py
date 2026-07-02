from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_config_show_help() -> None:
    assert_help_contains("lightning config show --help", "Usage: lightning config show", "Show configuration values.")
