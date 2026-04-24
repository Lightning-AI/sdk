from tests.cli.help import assert_help_contains


def test_license_list_help() -> None:
    assert_help_contains("lightning license list --help", "Usage: lightning license list", "List configured licenses.")
