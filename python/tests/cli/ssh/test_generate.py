from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_ssh_generate_help() -> None:
    assert_help_contains(
        "lightning ssh generate --help", "Usage: lightning ssh generate", "Get SSH config entry for a studio."
    )


@mock_command_logging
def test_generate_help() -> None:
    text = assert_help_contains(
        "lightning generate --help",
        "`lightning generate` has moved to noun-first commands:",
        "ssh -> lightning ssh generate",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_generate_ssh_legacy_help() -> None:
    assert_help_contains(
        "lightning generate ssh --help",
        "Deprecation warning:",
        "Use `lightning ssh generate` instead of `lightning generate ssh`.",
        "Usage: lightning generate ssh [OPTIONS]",
    )
