from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_list_studio():
    result_text = command_text("lightning studio list --help")

    assert "Usage: lightning studio list [OPTIONS]" in result_text
    assert "List Studios in a teamspace." in result_text
    assert "--teamspace  TEXT" in result_text
    assert "--all" in result_text
    assert "--sort-by" in result_text


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
