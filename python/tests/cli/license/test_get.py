from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_license_get_help() -> None:
    assert_help_contains(
        "lightning license get --help", "Usage: lightning license get", "Get a license key for a given product."
    )
