from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_license_download_help() -> None:
    assert_help_contains(
        "lightning license download --help",
        "Usage: lightning license download",
        "Download license for specific products/packages.",
    )


@mock_command_logging
def test_download_licenses_legacy_missing() -> None:
    text = command_text("lightning download licenses --help")
    assert "No such command 'licenses'." in text


@mock_command_logging
def test_download_license_legacy_missing() -> None:
    text = command_text("lightning download license --help")
    assert "No such command 'license'." in text
