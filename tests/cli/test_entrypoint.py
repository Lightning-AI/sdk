import os
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import login


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
