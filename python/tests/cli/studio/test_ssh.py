from tests.cli.help import assert_help_contains, command_text


def test_ssh_studio():
    result_text = command_text("lightning studio ssh --help")

    assert "Usage: lightning studio ssh [OPTIONS]" in result_text
    assert "SSH into a Studio." in result_text
    assert "--name           TEXT" in result_text
    assert "--teamspace      TEXT" in result_text
    assert "--option     -o  TEXT" in result_text


def test_studios_ssh_help() -> None:
    assert_help_contains("lightning studios ssh --help", "Usage: lightning studios ssh", "SSH into a Studio.")


def test_connect_help() -> None:
    text = assert_help_contains(
        "lightning connect --help",
        "`lightning connect` has moved to noun-first commands:",
        "studio -> lightning studio ssh",
    )
    assert "Deprecation warning:" not in text


def test_connect_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning connect studio --help",
        "Deprecation warning:",
        "Use `lightning studio ssh` instead of `lightning connect studio`.",
        "Usage: lightning connect studio [OPTIONS]",
    )
