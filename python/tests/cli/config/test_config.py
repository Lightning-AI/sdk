from tests.cli.help import assert_help_contains


def test_config_help() -> None:
    assert_help_contains("lightning config --help", "Usage: lightning config", "Manage SDK and CLI settings.")
