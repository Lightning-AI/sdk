from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_folder_download_help() -> None:
    assert_help_contains(
        "lightning folder download --help",
        "Usage: lightning folder download",
        "Download a folder from a Studio or a Teamspace drive folder.",
    )


@mock_command_logging
def test_folders_download_help() -> None:
    assert_help_contains(
        "lightning folders download --help",
        "Usage: lightning folders download",
        "Download a folder from a Studio or a Teamspace drive folder.",
    )


@mock_command_logging
def test_download_folder_legacy_help() -> None:
    assert_help_contains(
        "lightning download folder --help",
        "Deprecation warning:",
        "Use `lightning cp -r` instead of `lightning download folder`.",
        "Usage: lightning download folder [OPTIONS] SOURCE [DESTINATION]",
    )
