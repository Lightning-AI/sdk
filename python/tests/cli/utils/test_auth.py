import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.legacy.deploy._auth import _AuthLitServe, _AuthMode
from lightning_sdk.cli.utils.auth import browser_authentication, logout_session, require_auth_header
from lightning_sdk.lightning_cloud.login import Auth


def test_require_auth_header_uses_environment_credentials() -> None:
    """An environment header must be used without loading or authenticating."""
    auth = MagicMock(auth_header="Basic encoded")

    with patch("lightning_sdk.cli.utils.auth.Auth", return_value=auth):
        assert require_auth_header() == "Basic encoded"

    auth.load.assert_not_called()
    auth.authenticate.assert_not_called()


def test_require_auth_header_loads_saved_credentials() -> None:
    """Saved credentials must work without starting browser authentication."""
    auth = MagicMock()
    type(auth).auth_header = PropertyMock(side_effect=[ValueError("missing"), "Bearer token"])
    auth.load.return_value = True

    with patch("lightning_sdk.cli.utils.auth.Auth", return_value=auth):
        assert require_auth_header() == "Bearer token"

    auth.authenticate.assert_not_called()


def test_require_auth_header_instructs_login_without_opening_browser() -> None:
    """Missing credentials must stop ordinary commands and direct users to login."""
    auth = MagicMock()
    type(auth).auth_header = PropertyMock(side_effect=ValueError("missing"))
    auth.load.return_value = False

    with patch("lightning_sdk.cli.utils.auth.Auth", return_value=auth), pytest.raises(
        click.UsageError, match="lightning login"
    ):
        require_auth_header()

    auth.authenticate.assert_not_called()


def test_browser_authentication_blocks_subclass_callback_server() -> None:
    """The guard must also block SDK auth subclasses with custom callback servers."""

    class CustomAuth(Auth):
        browser_started = False

        def load(self) -> bool:
            return False

        def _run_server(self) -> None:
            self.browser_started = True

    auth = CustomAuth(api_key="", auth_token="")

    with browser_authentication(False), pytest.raises(ValueError, match="lightning login"):
        auth.authenticate()

    assert not auth.browser_started


def test_litserve_auth_uses_saved_credentials_without_starting_callback_server() -> None:
    """Deployment authentication must not start callback auth when credentials exist."""
    auth = _AuthLitServe(_AuthMode.DEPLOY)
    auth.api_key = "key"

    with patch.object(
        auth,
        "_run_server",
        side_effect=AssertionError("callback server must not start"),
    ):
        assert auth.authenticate().startswith("Bearer ")


def test_litserve_auth_instructs_login_when_callback_auth_would_be_required() -> None:
    """Deployment callback auth must tell the user to run the explicit login command."""
    with pytest.raises(click.UsageError, match="lightning login"):
        _AuthLitServe(_AuthMode.DEPLOY)._run_server()


def test_auth_save_stores_session_token_as_auth_token(monkeypatch, tmp_path) -> None:
    """Browser login callback passes the session token as `token`; it must be saved as `auth_token`."""
    secrets_file = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets_file)
    monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)

    auth = Auth()
    auth.save(token="sess_user-1.secret", user_id="user-1", api_key="")

    assert auth.auth_token == "sess_user-1.secret"
    assert auth.api_key == ""
    assert auth.auth_header == "Bearer sess_user-1.secret"
    assert json.loads(secrets_file.read_text()) == {
        "user_id": "user-1",
        "api_key": "",
        "auth_token": "sess_user-1.secret",
    }
    assert (secrets_file.stat().st_mode & 0o777) == 0o600


def test_logout_session_revokes_server_session_and_clears_credentials(monkeypatch, tmp_path) -> None:
    """`lightning logout` revokes the saved session token on the server and removes local credentials."""
    secrets_file = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets_file)
    monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)

    auth = Auth()
    auth.save(token="sess_user-1.secret", user_id="user-1")

    with patch("lightning_sdk.cli.utils.auth.requests.post") as post_mock:
        logout_session(Auth())

    post_mock.assert_called_once()
    assert post_mock.call_args.kwargs["headers"] == {"Authorization": "Bearer sess_user-1.secret"}
    assert not secrets_file.exists()
