from tests.cli.help import assert_help_contains, mock_command_logging


def test_legacy_configure_requires_login_without_authentication_fallback() -> None:
    """Legacy SSH configuration must not start callback authentication when credentials are missing."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.legacy.configure import _configure_ssh_internal

    auth = MagicMock()
    auth.authenticate.side_effect = AssertionError("callback authentication must not start")
    with patch(
        "lightning_sdk.cli.legacy.configure.require_auth_header",
        side_effect=click.UsageError("Run `lightning login` first."),
    ), patch("lightning_sdk.cli.legacy.configure.Auth", return_value=auth), pytest.raises(
        click.UsageError, match="lightning login"
    ):
        _configure_ssh_internal()

    auth.authenticate.assert_not_called()


def test_legacy_connect_reaches_non_browser_credential_boundary() -> None:
    """Legacy Studio connect must fail before its SSH subprocess when login is required."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.legacy.connect import studio

    auth = MagicMock()
    auth.authenticate.side_effect = AssertionError("callback authentication must not start")
    with patch(
        "lightning_sdk.cli.legacy.configure.require_auth_header",
        side_effect=click.UsageError("Run `lightning login` first."),
    ), patch("lightning_sdk.cli.legacy.configure.Auth", return_value=auth), patch(
        "lightning_sdk.cli.legacy.connect.subprocess.run",
        side_effect=AssertionError("SSH must not start without credentials"),
    ), pytest.raises(click.UsageError, match="lightning login"):
        studio.callback(name=None, teamspace=None)

    auth.authenticate.assert_not_called()


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
    ), patch("lightning_sdk.cli.ssh.configure.Auth", auth), pytest.raises(click.UsageError, match="Unknown studio"):
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
