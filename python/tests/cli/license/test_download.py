from tests.cli.help import assert_help_contains, command_text


def test_license_download_help() -> None:
    assert_help_contains(
        "lightning license download --help",
        "Usage: lightning license download",
        "Download license for specific products/packages.",
    )


def test_download_licenses_legacy_missing() -> None:
    text = command_text("lightning download licenses --help")
    assert "No such command 'licenses'." in text


def test_download_license_legacy_missing() -> None:
    text = command_text("lightning download license --help")
    assert "No such command 'license'." in text
