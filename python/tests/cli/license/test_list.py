from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_license_list_help() -> None:
    assert_help_contains("lightning license list --help", "Usage: lightning license list", "List configured licenses.")
