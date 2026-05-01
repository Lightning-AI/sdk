from tests.cli.help import assert_help_contains


def test_ssh_configure_help() -> None:
    assert_help_contains(
        "lightning ssh configure --help", "Usage: lightning ssh configure", "Get SSH config entry for a studio."
    )


def test_configure_help() -> None:
    text = assert_help_contains(
        "lightning configure --help",
        "`lightning configure` has moved to noun-first commands:",
        "ssh -> lightning ssh configure",
    )
    assert "Deprecation warning:" not in text


def test_configure_ssh_legacy_help() -> None:
    assert_help_contains(
        "lightning configure ssh --help",
        "Deprecation warning:",
        "Use `lightning ssh configure` instead of `lightning configure ssh`.",
        "Usage: lightning configure ssh [OPTIONS]",
    )
