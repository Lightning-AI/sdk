from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_license_download_all_help() -> None:
    assert_help_contains(
        "lightning license download-all --help",
        "Usage: lightning license download-all",
        "Download licenses for all user's products/packages.",
    )
