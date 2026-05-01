from tests.cli.help import assert_help_contains


def test_base_studio_help() -> None:
    assert_help_contains(
        "lightning base-studio --help", "Usage: lightning base-studio", "Manage Lightning AI Base Studios."
    )


def test_base_studios_help() -> None:
    assert_help_contains(
        "lightning base-studios --help", "Usage: lightning base-studios", "Manage Lightning AI Base Studios."
    )
