from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_license_help() -> None:
    assert_help_contains("lightning license --help", "Usage: lightning license", "View and manage product licenses.")
