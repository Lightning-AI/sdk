from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_switch_studio():
    result_text = command_text("lightning studio switch --help")
    assert "Usage: lightning studio switch [OPTIONS]" in result_text
    assert "Switch a Studio to a different machine type." in result_text
    assert "--name           TEXT" in result_text
    assert "--teamspace      TEXT" in result_text
    assert "--machine" in result_text
    assert "--interruptible" in result_text


@mock_command_logging
def test_studios_switch_help() -> None:
    assert_help_contains(
        "lightning studios switch --help",
        "Usage: lightning studios switch",
        "Switch a Studio to a different machine type.",
    )


@mock_command_logging
def test_switch_help() -> None:
    text = assert_help_contains(
        "lightning switch --help",
        "`lightning switch` has moved to noun-first commands:",
        "studio -> lightning studio switch",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_switch_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning switch studio --help",
        "Deprecation warning:",
        "Use `lightning studio switch` instead of `lightning switch studio`.",
        "Usage: lightning switch studio [OPTIONS]",
    )
