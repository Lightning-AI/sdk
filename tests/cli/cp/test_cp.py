from tests.cli.help import assert_help_contains


def test_cp_help() -> None:
    assert_help_contains(
        "lightning cp --help",
        "Usage: lightning cp [OPTIONS] SOURCE [DESTINATION]",
        "Copy files between local filesystem, Studios, and teamspace drives.",
    )
