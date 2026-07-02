from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_api_help() -> None:
    assert_help_contains("lightning api --help", "Usage: lightning api", "Manage Lightning AI APIs.")


@mock_command_logging
def test_apis_help() -> None:
    assert_help_contains("lightning apis --help", "Usage: lightning apis", "Manage Lightning AI APIs.")
