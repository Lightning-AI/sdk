import os
import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import login
from tests.cli.help import assert_help_contains


def test_help():
    result_text = assert_help_contains(
        "lightning --help",
        "Usage: lightning [OPTIONS] COMMAND [ARGS]...",
        "  base-studio  Manage Lightning AI Base Studios.",
        "  api-key      Manage API keys for public model endpoints.",
        "  config       Manage Lightning SDK and CLI configuration.",
        "  cp           Copy files between local filesystem, Studios,",
        "  container    Manage Lightning AI containers.",
        "  file         Manage file transfers.",
        "  folder       Manage folder transfers.",
        "  job          Manage Lightning AI Jobs.",
        "  license      Manage Lightning AI Product Licenses.",
        "  machine      Manage Lightning AI machine types.",
        "  mmt          Manage Lightning AI Multi-Machine Training (MMT).",
        "  model        Manage Lightning AI Models.",
        "  ssh          Manage SSH configuration.",
        "  studio       Manage Lightning AI Studios.",
        "  vm           Manage Lightning AI VMs.",
    )
    assert "  create" not in result_text
    assert "  delete" not in result_text
    assert "  download" not in result_text
    assert not any(line.startswith("  api ") for line in result_text.splitlines())
    assert "  jobs" not in result_text
    assert "  open" not in result_text
    assert "  run" not in result_text
    assert "  studios" not in result_text
    assert "  upload" not in result_text


def test_help_uvx():
    result = subprocess.run("uvx --with-editable=../ lightning-sdk --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    if "Usage: lightning-sdk [OPTIONS] COMMAND [ARGS]..." in result_text:
        assert not any(line.startswith("  api ") for line in result_text.splitlines())
        assert "  cp           Copy files between local filesystem, Studios," in result_text
        assert "  container    Manage Lightning AI containers." in result_text
        assert "  job          Manage Lightning AI Jobs." in result_text
        assert "  license      Manage Lightning AI Product Licenses." in result_text
        assert "  machine      Manage Lightning AI machine types." in result_text
        assert "  mmt          Manage Lightning AI Multi-Machine Training (MMT)." in result_text
        assert "  ssh          Manage SSH configuration." in result_text
        assert "  studio       Manage Lightning AI Studios." in result_text
        return

    assert "does not appear" in result_text
    assert "to be a Python project" in result_text


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


def test_login_help():
    result_text = assert_help_contains("lightning login --help", "Usage: lightning login [OPTIONS]")

    assert "Login to Lightning AI Studios." in result_text


def test_logout_help():
    result_text = assert_help_contains("lightning logout --help", "Usage: lightning logout [OPTIONS]")

    assert "Logout from Lightning AI Studios." in result_text


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
