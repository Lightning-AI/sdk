from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.legacy.deploy._auth import _AuthLitServe, _AuthMode
from lightning_sdk.cli.utils.auth import require_auth_header


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


def test_litserve_auth_uses_saved_credentials_without_starting_callback_server() -> None:
    """Deployment authentication must not start callback auth when credentials exist."""
    auth = _AuthLitServe(_AuthMode.DEPLOY)
    auth.user_id = "user"
    auth.api_key = "key"

    with patch.object(
        auth,
        "_run_server",
        side_effect=AssertionError("callback server must not start"),
    ):
        assert auth.authenticate().startswith("Basic ")


def test_litserve_auth_instructs_login_when_callback_auth_would_be_required() -> None:
    """Deployment callback auth must tell the user to run the explicit login command."""
    with pytest.raises(click.UsageError, match="lightning login"):
        _AuthLitServe(_AuthMode.DEPLOY)._run_server()
