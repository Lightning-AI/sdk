from unittest.mock import MagicMock

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import login


def test_login_in_studio(monkeypatch):
    """Test login command when running inside a Studio."""
    monkeypatch.setenv("LIGHTNING_CLOUD_SPACE_ID", "cloud-space-id")
    monkeypatch.setenv("LIGHTNING_INTERACTIVE", "true")

    mock_user = MagicMock()
    mock_user.name = "Test User"
    monkeypatch.setattr("lightning_sdk.cli.entrypoint._get_authed_user", lambda: mock_user)

    mock_auth_cls = MagicMock()
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", mock_auth_cls)

    runner = CliRunner()
    result = runner.invoke(login)

    assert result.exit_code == 0
    assert 'You are currently logged in as "Test User"' in result.output
    assert '"lightning login" is not required within a Studio' in result.output

    # Verify Auth was not instantiated
    mock_auth_cls.assert_not_called()


def test_login_outside_studio(monkeypatch):
    """Test login command when running outside a Studio."""
    mock_auth_instance = MagicMock()
    mock_auth_cls = MagicMock(return_value=mock_auth_instance)
    monkeypatch.setattr("lightning_sdk.cli.entrypoint.Auth", mock_auth_cls)

    runner = CliRunner()
    result = runner.invoke(login)

    assert result.exit_code == 0

    # Verify Auth was called
    mock_auth_cls.assert_called_once()
    mock_auth_instance.clear.assert_called_once()
    mock_auth_instance.authenticate.assert_called_once()
