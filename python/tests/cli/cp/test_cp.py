from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_cp_help() -> None:
    assert_help_contains(
        "lightning cp --help",
        "Usage: lightning cp [OPTIONS] SOURCE [DESTINATION]",
        "Copy between local, Studios, Drive.",
    )
