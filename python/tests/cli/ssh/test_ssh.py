from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_ssh_help() -> None:
    assert_help_contains("lightning ssh --help", "Usage: lightning ssh", "Configure SSH access to Studios.")
