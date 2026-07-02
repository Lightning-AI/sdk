from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_container_help() -> None:
    assert_help_contains("lightning container --help", "Usage: lightning container", "Run and manage containers.")


@mock_command_logging
def test_containers_help() -> None:
    assert_help_contains("lightning containers --help", "Usage: lightning containers", "Run and manage containers.")
