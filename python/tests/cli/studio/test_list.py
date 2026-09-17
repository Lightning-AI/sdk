from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_list_studio():
    assert_help_contains(
        "lightning studio list --help",
        "Usage: lightning studio list [OPTIONS]",
        "List Studios in a teamspace.",
        "--teamspace TEXT",
        "--all",
        "--sort-by",
    )


@mock_command_logging
def test_studios_list_help() -> None:
    assert_help_contains(
        "lightning studios list --help", "Usage: lightning studios list", "List Studios in a teamspace."
    )


@mock_command_logging
def test_list_studios_legacy_help() -> None:
    assert_help_contains(
        "lightning list studios --help",
        "Deprecation warning:",
        "Use `lightning studio list` instead of `lightning list studios`.",
        "Usage: lightning list studios [OPTIONS]",
    )
