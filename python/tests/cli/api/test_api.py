from tests.cli.help import assert_help_contains


def test_api_help() -> None:
    assert_help_contains("lightning api --help", "Usage: lightning api", "Manage Lightning AI APIs.")


def test_apis_help() -> None:
    assert_help_contains("lightning apis --help", "Usage: lightning apis", "Manage Lightning AI APIs.")
