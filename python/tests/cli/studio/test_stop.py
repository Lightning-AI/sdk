from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_stop_studio():
    assert_help_contains(
        "lightning studio stop --help",
        "Usage: lightning studio stop [OPTIONS]",
        "Stop a Studio.",
        "--name TEXT",
        "--teamspace TEXT",
    )


@mock_command_logging
def test_studios_stop_help() -> None:
    assert_help_contains("lightning studios stop --help", "Usage: lightning studios stop", "Stop a Studio.")


@mock_command_logging
def test_stop_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning stop studio --help",
        "Deprecation warning:",
        "Use `lightning studio stop` instead of `lightning stop studio`.",
        "Usage: lightning stop studio [OPTIONS]",
    )
