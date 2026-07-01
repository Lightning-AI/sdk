from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_license_set_help() -> None:
    assert_help_contains(
        "lightning license set --help", "Usage: lightning license set", "Set a license key for a given product."
    )
