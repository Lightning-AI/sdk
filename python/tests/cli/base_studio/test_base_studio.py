from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_base_studio_help() -> None:
    assert_help_contains(
        "lightning base-studio --help", "Usage: lightning base-studio", "Reusable Studio environment images."
    )


@mock_command_logging
def test_base_studios_help() -> None:
    assert_help_contains(
        "lightning base-studios --help", "Usage: lightning base-studios", "Reusable Studio environment images."
    )
