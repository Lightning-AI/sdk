from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_switch_studio():
    assert_help_contains(
        "lightning studio switch --help",
        "Usage: lightning studio switch [OPTIONS]",
        "Switch a Studio to a different machine type.",
        "--name TEXT",
        "--teamspace TEXT",
        "--machine",
        "--interruptible",
    )


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
