from tests.cli.help import assert_help_contains


def test_license_help() -> None:
    assert_help_contains(
        "lightning license --help", "Usage: lightning license", "Manage Lightning AI Product Licenses."
    )
