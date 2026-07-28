from tests.cli.help import assert_help_contains, mock_command_logging


def test_configure_resolves_studio_before_authentication() -> None:
    """An unresolved studio does not start authentication or key downloads."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.ssh.configure import configure_ssh

    auth = MagicMock()
    with patch(
        "lightning_sdk.cli.ssh.configure.resolve_teamspace",
        return_value=MagicMock(),
    ), patch(
        "lightning_sdk.cli.ssh.configure.resolve_studio",
        side_effect=click.UsageError("Unknown studio"),
    ), patch("lightning_sdk.cli.ssh.configure.Auth", auth):
        with pytest.raises(click.UsageError, match="Unknown studio"):
            configure_ssh.callback(name="missing")

    auth.assert_not_called()


@mock_command_logging
def test_ssh_configure_help() -> None:
    assert_help_contains(
        "lightning ssh configure --help", "Usage: lightning ssh configure", "Get SSH config entry for a studio."
    )


@mock_command_logging
def test_configure_help() -> None:
    text = assert_help_contains(
        "lightning configure --help",
        "`lightning configure` has moved to noun-first commands:",
        "ssh -> lightning ssh configure",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_configure_ssh_legacy_help() -> None:
    assert_help_contains(
        "lightning configure ssh --help",
        "Deprecation warning:",
        "Use `lightning ssh configure` instead of `lightning configure ssh`.",
        "Usage: lightning configure ssh [OPTIONS]",
    )
