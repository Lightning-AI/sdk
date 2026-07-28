from tests.cli.help import assert_help_contains, command_text, mock_command_logging


def test_ssh_resolves_before_downloading_keys() -> None:
    """SSH lookup failures occur before key downloads."""
    from unittest.mock import MagicMock, patch

    import pytest
    import rich_click as click

    from lightning_sdk.cli.studio.ssh import ssh_impl

    configure = MagicMock()
    with patch(
        "lightning_sdk.cli.studio.ssh.resolve_teamspace",
        return_value=MagicMock(),
    ), patch(
        "lightning_sdk.cli.studio.ssh.resolve_studio",
        side_effect=click.UsageError("Pass --name STUDIO."),
    ), patch(
        "lightning_sdk.cli.studio.ssh.configure_ssh_internal",
        configure,
    ):
        with pytest.raises(click.UsageError, match="--name"):
            ssh_impl(name=None, teamspace=None, option=None)

    configure.assert_not_called()


@mock_command_logging
def test_ssh_studio():
    result_text = command_text("lightning studio ssh --help")

    assert "Usage: lightning studio ssh [OPTIONS]" in result_text
    assert "SSH into a Studio." in result_text
    assert "--name           TEXT" in result_text
    assert "--teamspace      TEXT" in result_text
    assert "--option     -o  TEXT" in result_text


@mock_command_logging
def test_studios_ssh_help() -> None:
    assert_help_contains("lightning studios ssh --help", "Usage: lightning studios ssh", "SSH into a Studio.")


@mock_command_logging
def test_connect_help() -> None:
    text = assert_help_contains(
        "lightning connect --help",
        "`lightning connect` has moved to noun-first commands:",
        "studio -> lightning studio ssh",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_connect_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning connect studio --help",
        "Deprecation warning:",
        "Use `lightning studio ssh` instead of `lightning connect studio`.",
        "Usage: lightning connect studio [OPTIONS]",
    )
