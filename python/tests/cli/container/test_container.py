from tests.cli.help import assert_help_contains


def test_container_help() -> None:
    assert_help_contains("lightning container --help", "Usage: lightning container", "Run and manage containers.")


def test_containers_help() -> None:
    assert_help_contains("lightning containers --help", "Usage: lightning containers", "Run and manage containers.")
