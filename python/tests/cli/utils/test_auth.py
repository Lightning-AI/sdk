from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.legacy.deploy._auth import _AuthLitServe, _AuthMode
from lightning_sdk.cli.utils.auth import browser_authentication, require_auth_header
from lightning_sdk.lightning_cloud.credentials import CredentialSource
from lightning_sdk.lightning_cloud.login import Auth


def _no_credentials(monkeypatch, tmp_path) -> None:
    for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN_FILE", str(tmp_path / "missing-token"))
    monkeypatch.setattr(Auth, "secrets_file", tmp_path / "credentials.json")
    monkeypatch.setattr(
        Auth,
        "_run_server",
        lambda self: (_ for _ in ()).throw(AssertionError("browser authentication reached")),
    )


def test_require_auth_header_uses_the_credential_source() -> None:
    """An available header must be returned without loading or authenticating."""
    auth = MagicMock(auth_header="Bearer token")

    with patch("lightning_sdk.cli.utils.auth.Auth", return_value=auth):
        assert require_auth_header() == "Bearer token"

    auth.load.assert_not_called()
    auth.authenticate.assert_not_called()


def test_require_auth_header_instructs_login_without_opening_browser() -> None:
    """Missing credentials must stop ordinary commands and direct users to login."""
    auth = MagicMock()
    type(auth).auth_header = PropertyMock(
        side_effect=ValueError("No Lightning credentials are available. Run `lightning login` first.")
    )

    with patch("lightning_sdk.cli.utils.auth.Auth", return_value=auth), pytest.raises(
        click.UsageError, match="lightning login"
    ):
        require_auth_header()

    auth.authenticate.assert_not_called()


def test_browser_authentication_blocks_the_source_from_opening_a_browser(monkeypatch, tmp_path) -> None:
    _no_credentials(monkeypatch, tmp_path)

    with browser_authentication(False), pytest.raises(ValueError, match="Run `lightning login` first"):
        CredentialSource().header()


def test_browser_authentication_allows_the_source_to_open_a_browser(monkeypatch, tmp_path) -> None:
    _no_credentials(monkeypatch, tmp_path)
    started = []
    monkeypatch.setattr(Auth, "_run_server", lambda self: started.append(True))

    with browser_authentication(True), pytest.raises(ValueError, match="couldn't find any credentials"):
        CredentialSource().header()

    assert started == [True]


def test_litserve_auth_uses_the_credential_source(monkeypatch) -> None:
    """Deployment authentication must not start callback auth when a credential exists."""
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "token")
    auth = _AuthLitServe(_AuthMode.DEPLOY)

    with patch.object(auth, "_run_server", side_effect=AssertionError("callback server must not start")):
        assert auth.authenticate() == "Bearer token"


def test_litserve_auth_instructs_login_when_callback_auth_would_be_required(monkeypatch, tmp_path) -> None:
    """Deployment callback auth must tell the user to run the explicit login command."""
    _no_credentials(monkeypatch, tmp_path)

    with browser_authentication(False), pytest.raises(click.UsageError, match="lightning login"):
        _AuthLitServe(_AuthMode.DEPLOY)._run_server()
