from tests.cli.help import assert_help_contains, command_text


def test_delete_studio():
    result_text = command_text("lightning studio delete --help")

    assert "Usage: lightning studio delete [OPTIONS]" in result_text
    assert "Delete a Studio." in result_text
    assert "--name       TEXT" in result_text
    assert "--teamspace  TEXT" in result_text


def test_studios_delete_help() -> None:
    assert_help_contains("lightning studios delete --help", "Usage: lightning studios delete", "Delete a Studio.")


def test_delete_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning delete studio --help",
        "Deprecation warning:",
        "Use `lightning studio delete` instead of `lightning delete studio`.",
        "Usage: lightning delete studio [OPTIONS]",
    )
