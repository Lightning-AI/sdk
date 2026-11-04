import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import rich_click as click

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
    ), pytest.raises(click.UsageError, match="--name"):
        ssh_impl(name=None, teamspace=None, option=None)

    configure.assert_not_called()


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="needs OpenSSH's ssh-keygen")
def test_ssh_uses_the_local_key_and_registers_it(tmp_path, monkeypatch) -> None:
    """The key is made on this machine once, registered on each run, and passed to ssh as is."""
    from lightning_sdk.cli.studio.ssh import ssh_impl

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    studio = MagicMock()
    studio._studio.id = "studio-id"
    api = MagicMock()
    run = MagicMock()
    real_run = subprocess.run

    def run_all_but_ssh(command, **kwargs):
        return run(command, **kwargs) if command[0] == "ssh" else real_run(command, **kwargs)

    with patch("lightning_sdk.cli.studio.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.studio.ssh.resolve_studio", return_value=studio
    ), patch("lightning_sdk.cli.studio.ssh.save_studio_to_config"), patch(
        "lightning_sdk.cli.utils.ssh_connection.require_auth_header", return_value="Bearer token"
    ), patch("lightning_sdk.cli.utils.ssh_connection.SSHKeyApi", return_value=api), patch(
        "lightning_sdk.cli.studio.ssh.subprocess.run", run_all_but_ssh
    ):
        ssh_impl(name="dev", teamspace=None, option=["StrictHostKeyChecking no", "LogLevel=ERROR"])
        ssh_impl(name="dev", teamspace=None, option=None)

    key_path = str(tmp_path / ".ssh" / "lightning_ed25519")
    public_key = (tmp_path / ".ssh" / "lightning_ed25519.pub").read_text().strip()
    assert [c.kwargs["public_key"] for c in api.create_public_key.call_args_list] == [public_key, public_key]
    assert run.call_args_list[0].args[0] == [
        "ssh",
        "-i",
        key_path,
        "-o",
        "StrictHostKeyChecking no",
        "-o",
        "LogLevel=ERROR",
        "s_studio-id@ssh.lightning.ai",
    ]
    assert run.call_args_list[1].args[0] == ["ssh", "-i", key_path, "s_studio-id@ssh.lightning.ai"]


def test_ssh_reports_a_missing_ssh_client() -> None:
    from lightning_sdk.cli.studio.ssh import ssh_impl

    with patch("lightning_sdk.cli.studio.ssh.resolve_teamspace", return_value=MagicMock()), patch(
        "lightning_sdk.cli.studio.ssh.resolve_studio", return_value=MagicMock()
    ), patch("lightning_sdk.cli.studio.ssh.save_studio_to_config"), patch(
        "lightning_sdk.cli.studio.ssh.configure_ssh_internal", return_value="/tmp/key"
    ) as configure, patch(
        "lightning_sdk.cli.studio.ssh.subprocess.run", side_effect=FileNotFoundError("ssh")
    ), pytest.raises(click.ClickException, match="Failed to establish SSH connection"):
        ssh_impl(name="dev", teamspace=None, option=None)

    configure.assert_called_once_with()


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
