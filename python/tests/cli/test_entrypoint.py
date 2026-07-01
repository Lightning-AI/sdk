import os
import re
import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import login
from tests.cli.help import assert_help_contains, mock_command_logging, run_cli

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_BOX_CHARS_RE = re.compile(r"[│╭╰╮─╯]")


def _help_text() -> str:
    """Return help output with each command's wrapped description joined onto one line.

    The rich-click layout renders two side-by-side panels separated by ││.
    We split each row into left and right cells, process each column
    independently so that continuation lines (leading spaces > 3) are merged
    into the preceding command entry, and return the reconstructed lines.
    """
    result = run_cli("lightning --help")
    raw = _ANSI_ESCAPE_RE.sub("", result.stdout)

    # Locate the column split from the first row that contains ││
    split = -1
    for line in raw.splitlines():
        pos = line.find("││")
        if pos >= 0:
            split = pos + 1
            break

    left_cells: list[tuple[str, bool]] = []
    right_cells: list[tuple[str, bool]] = []
    for line in raw.splitlines():
        is_panel = "│" in line
        if split > 0 and len(line) > split and is_panel:
            left_cells.append((line[:split], True))
            right_cells.append((line[split:], True))
        else:
            left_cells.append((line, False))
            right_cells.append(("", False))

    def _join_cells(cells: list[tuple[str, bool]]) -> list[str]:
        entries: list[str] = []
        for cell, is_panel in cells:
            content = _BOX_CHARS_RE.sub(" ", cell)
            stripped = content.lstrip()
            leading = len(content) - len(stripped)
            value = stripped.rstrip()
            if not value:
                continue
            # Panel continuation lines have the command-name column empty (> 3 spaces).
            # Non-panel lines (headers, usage, separators) are never continuations.
            if is_panel and leading > 3 and entries:
                entries[-1] = entries[-1].rstrip() + " " + value
            else:
                entries.append(value)
        return entries

    return "\n".join(_join_cells(left_cells) + _join_cells(right_cells))


@mock_command_logging
def test_help():
    text = _help_text()

    assert "Usage: lightning [OPTIONS] COMMAND [ARGS]..." in text

    # GET STARTED
    assert "login     Sign in to Lightning AI." in text
    assert "logout    Sign out of the current session." in text
    assert "config    Manage SDK and CLI settings." in text

    # COMPUTE
    assert "studio    Persistent GPU dev workspaces." in text
    assert "base-st…  Reusable Studio environment images." in text
    assert "vm        Bare VMs with SSH access." in text
    assert "machine   Browse GPU and CPU machine types." in text
    assert "contain…  Run and manage containers." in text
    assert "sandbox   Ephemeral sandboxes for agents." in text

    # TRAIN & DEPLOY
    assert "job       Run batch jobs and sweeps." in text
    assert "mmt       Multi-node distributed training." in text
    assert "model     Register and version models." in text
    assert "deploym…  Deploy autoscaling inference APIs." in text

    # ACCESS
    assert "api-key   Keys for model endpoint access." in text
    assert "ssh       Configure SSH access to Studios." in text
    assert "license   View and manage product licenses." in text

    # DATA & FILES
    assert "cp        Copy between local, Studios, Drive." in text
    assert "file      Upload and download files." in text
    assert "folder    Upload and download folders." in text

    # Hidden commands should not appear
    assert "  create" not in text
    assert "  delete" not in text
    assert "  download" not in text
    assert not any(line.startswith("  api ") for line in text.splitlines())
    assert "  jobs" not in text
    assert "  open" not in text
    assert "  run" not in text
    assert "  studios" not in text
    assert "  upload" not in text


@mock_command_logging
def test_help_uvx():
    result = subprocess.run("uvx --with-editable=../ lightning-sdk --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    if "Usage: lightning-sdk [OPTIONS] COMMAND [ARGS]..." in result_text:
        assert not any(line.startswith("  api ") for line in result_text.splitlines())
        assert "cp        Copy between local," in result_text
        assert "contain…  Run and manage containers." in result_text
        assert "job       Run batch jobs and sweeps." in result_text
        assert "license   View and manage product" in result_text
        assert "machine   Browse GPU and CPU machine" in result_text
        assert "mmt       Multi-node distributed" in result_text
        assert "sandbox   Ephemeral sandboxes for" in result_text
        assert "ssh       Configure SSH access to" in result_text
        assert "studio    Persistent GPU dev" in result_text
        return


@mock_command_logging
def test_login_already_authed_can_get_username(monkeypatch):
    """Test login command when already authed."""

    mock_user = MagicMock()
    mock_user.name = "Test User"
    monkeypatch.setattr("lightning_sdk.cli.entrypoint._get_authed_user", lambda: mock_user)

    mock_auth_instance = MagicMock()
    mock_auth_cls = MagicMock(return_value=mock_auth_instance)
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", mock_auth_cls)

    runner = CliRunner()
    result = runner.invoke(login)

    assert result.exit_code == 0
    assert 'You are currently logged in as "Test User"' in result.output
    assert '"lightning login" is not required within a Studio or when already logged in' in result.output

    # Verify Auth was not instantiated
    mock_auth_cls.assert_called_once()
    mock_auth_instance.clear.assert_not_called()
    mock_auth_instance.authenticate.assert_not_called()


@mock_command_logging
def test_login_help():
    result_text = assert_help_contains("lightning login --help", "Usage: lightning login [OPTIONS]")

    assert "Sign in to Lightning AI." in result_text


@mock_command_logging
def test_logout_help():
    result_text = assert_help_contains("lightning logout --help", "Usage: lightning logout [OPTIONS]")

    assert "Sign out of the current session." in result_text


@mock_command_logging
def test_login_already_authed_cannot_get_username(monkeypatch):
    """Test login command when already authed."""

    def _get_authed_user_mock():
        raise Exception("Test Error")

    monkeypatch.setattr("lightning_sdk.cli.entrypoint._get_authed_user", _get_authed_user_mock)

    mock_auth_cls = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", mock_auth_cls)

    runner = CliRunner()
    result = runner.invoke(login)

    assert result.exit_code == 0
    assert "You are already logged in" in result.output
    assert "Test User" not in result.output
    assert '"lightning login" is not required within a Studio or when already logged in' in result.output


@patch.dict(os.environ, {"LIGHTNING_INTERACTIVE": "true", "LIGHTNING_CLOUD_SPACE_ID": "cloud-space-id"}, clear=True)
@mock_command_logging
def test_cannot_login_within_studio(monkeypatch):
    mock_auth_instance = MagicMock()
    mock_auth_cls = MagicMock(return_value=mock_auth_instance)
    # Ensure auth appears as not logged in
    mock_auth_instance.user_id = None
    mock_auth_instance.api_key = None
    mock_auth_instance.load.return_value = False
    mock_auth_instance.authenticate.side_effect = RuntimeError("Test Error")
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", mock_auth_cls)

    runner = CliRunner()
    result = runner.invoke(login)
    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert "Unable to login within a Studio. Did you change your shell setup?" in str(result.exception)


@patch.dict(os.environ, {}, clear=True)
@mock_command_logging
def test_login_not_authed_outside_studio(monkeypatch):
    """Test login command when not authed outsice a Studio."""
    mock_auth_instance = MagicMock()
    mock_auth_cls = MagicMock(return_value=mock_auth_instance)
    # Ensure auth appears as not logged in
    mock_auth_instance.user_id = None
    mock_auth_instance.api_key = None
    mock_auth_instance.load.return_value = False
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", mock_auth_cls)

    runner = CliRunner()
    result = runner.invoke(login)

    assert result.exit_code == 0

    # Verify Auth was called
    mock_auth_cls.assert_called_once()
    mock_auth_instance.clear.assert_called_once()
    mock_auth_instance.authenticate.assert_called_once()
