from tests.cli.help import assert_help_contains, command_text


def test_stop_studio():
    result_text = command_text("lightning studio stop --help")

    assert "Usage: lightning studio stop [OPTIONS]" in result_text
    assert "Stop a Studio." in result_text
    assert "--name TEXT" in result_text
    assert "--teamspace TEXT" in result_text


def test_studios_stop_help() -> None:
    assert_help_contains("lightning studios stop --help", "Usage: lightning studios stop", "Stop a Studio.")


def test_stop_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning stop studio --help",
        "Deprecation warning:",
        "Use `lightning studio stop` instead of `lightning stop studio`.",
        "Usage: lightning stop studio [OPTIONS]",
    )
