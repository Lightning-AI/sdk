import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import rich_click as click

from lightning_sdk.cli.legacy.deploy._auth import _AuthLitServe, _AuthMode
from lightning_sdk.cli.utils.auth import (
    browser_authentication,
    login_with_device_code,
    logout_session,
    require_auth_header,
)
from lightning_sdk.lightning_cloud.login import Auth

_DEVICE_GRANT = {
    "device_code": "device-code",
    "user_code": "BCDF-GHJK",
    "verification_uri": "https://lightning.ai/device",
    "expires_in": 600,
    "interval": 5,
}


def _response(status_code: int, body=None, json_error=None) -> MagicMock:
    response = MagicMock(status_code=status_code, ok=status_code < 400)
    response.json.side_effect = json_error
    response.json.return_value = body
    return response


def _device_login_env(monkeypatch, tmp_path, responses: list) -> tuple:
    """Point credentials at tmp_path, answer HTTP calls from `responses`, and record sleeps instead of sleeping."""
    secrets_file = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets_file)
    for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    post = MagicMock(side_effect=responses)
    sleeps: list = []
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.post", post)
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.time.sleep", sleeps.append)
    return secrets_file, post, sleeps


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


def test_login_with_browser_redirects_without_credentials_in_url(monkeypatch, tmp_path) -> None:
    """The `/login-complete` callback redirects to `/cli-login-successful` without forwarding tokens in the URL."""
    import asyncio

    from lightning_sdk.lightning_cloud.login import AuthServer

    secrets_file = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets_file)
    monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)

    captured: dict = {}

    class FakeServer:
        def __init__(self, config) -> None:
            captured["app"] = config.app

        def run(self) -> None:
            route = next(r for r in captured["app"].routes if getattr(r, "path", None) == "/login-complete")
            resp = asyncio.run(
                route.endpoint(token="sess_user-1.secret", key="", state="fixed-state", user_id="user-1")
            )
            captured["location"] = resp.headers["location"]

    monkeypatch.setattr("lightning_sdk.cli.utils.auth._generate_state", lambda: "fixed-state")
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.head", MagicMock())
    monkeypatch.setattr("webbrowser.open", lambda url: captured.setdefault("auth_url", url) or True)
    monkeypatch.setattr("uvicorn.Server", FakeServer)

    auth = Auth()
    AuthServer().login_with_browser(auth)

    assert "state=fixed-state" in captured["auth_url"] or "state%3Dfixed-state" in captured["auth_url"]
    assert captured["location"].endswith("/cli-login-successful")
    assert "token=" not in captured["location"]
    assert auth.auth_token == "sess_user-1.secret"


def test_login_with_browser_rejects_callback_without_matching_state(monkeypatch, tmp_path) -> None:
    """Omitting or forging `state` must not store the callback token or key."""
    import asyncio

    from lightning_sdk.lightning_cloud.login import AuthServer

    secrets_file = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets_file)
    monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)

    captured: dict = {}

    class FakeServer:
        def __init__(self, config) -> None:
            captured["app"] = config.app

        def run(self) -> None:
            captured["route"] = next(r for r in captured["app"].routes if getattr(r, "path", None) == "/login-complete")

    monkeypatch.setattr("lightning_sdk.cli.utils.auth._generate_state", lambda: "fixed-state")
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.head", MagicMock())
    monkeypatch.setattr("webbrowser.open", lambda url: True)
    monkeypatch.setattr("uvicorn.Server", FakeServer)

    auth = Auth()
    AuthServer().login_with_browser(auth)

    for state in ("", "forged-state"):
        resp = asyncio.run(
            captured["route"].endpoint(
                token="sess_attacker.secret", key="attacker-key", state=state, user_id="attacker"
            )
        )
        assert resp.headers["location"].endswith("/cli-login-failed")

    assert not secrets_file.exists()
    assert not auth.auth_token
    assert not auth.api_key


def test_login_with_device_code_saves_the_approved_session(monkeypatch, tmp_path, capsys) -> None:
    """The CLI polls at the server's interval, backs off on `slow_down`, and saves the session it is given."""
    secrets_file, post, sleeps = _device_login_env(
        monkeypatch,
        tmp_path,
        [
            _response(200, _DEVICE_GRANT),
            _response(400, {"error": "authorization_pending"}),
            _response(400, {"error": "slow_down"}),
            _response(200, {"access_token": "sess_user-1.secret", "token_type": "Bearer", "expires_in": 604800}),
        ],
    )

    login_with_device_code(Auth())

    assert sleeps == [5, 5, 10]
    assert post.call_args_list[0].args[0].endswith("/oidc/device_authorization")
    assert post.call_args_list[0].kwargs["data"] == {"client_id": "lightning-cli"}
    for poll in post.call_args_list[1:]:
        assert poll.args[0].endswith("/oidc/token")
        assert poll.kwargs["data"] == {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": "device-code",
            "client_id": "lightning-cli",
        }
    output = capsys.readouterr().out
    assert "https://lightning.ai/device" in output
    assert "BCDF-GHJK" in output
    assert json.loads(secrets_file.read_text())["auth_token"] == "sess_user-1.secret"
    assert (secrets_file.stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize(
    ("poll", "message"),
    [
        (_response(400, {"error": "access_denied"}), "denied in the browser"),
        (_response(400, {"error": "expired_token"}), "code expired"),
        (_response(400, {"error": "invalid_grant"}), "invalid_grant"),
    ],
)
def test_login_with_device_code_stops_when_the_server_refuses(monkeypatch, tmp_path, poll, message) -> None:
    secrets_file, _, _ = _device_login_env(monkeypatch, tmp_path, [_response(200, _DEVICE_GRANT), poll])

    with pytest.raises(RuntimeError, match=message):
        login_with_device_code(Auth())

    assert not secrets_file.exists()


def test_login_with_device_code_gives_up_when_the_code_expires(monkeypatch, tmp_path) -> None:
    """Polling stops at `expires_in` even if the server never says the code expired."""
    secrets_file, post, _ = _device_login_env(
        monkeypatch, tmp_path, [_response(200, _DEVICE_GRANT), _response(400, {"error": "authorization_pending"})]
    )
    clock = iter([0, 300])
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.time.monotonic", lambda: next(clock, 600))

    with pytest.raises(RuntimeError, match="code expired"):
        login_with_device_code(Auth())

    assert post.call_count == 2
    assert not secrets_file.exists()


@pytest.mark.parametrize(
    "start",
    [_response(404, {"code": 5}), _response(200, json_error=ValueError("an HTML page"))],
    ids=["not found", "web app page"],
)
def test_login_with_device_code_explains_a_server_without_it(monkeypatch, tmp_path, start) -> None:
    _device_login_env(monkeypatch, tmp_path, [start])

    with pytest.raises(RuntimeError, match="may not support `lightning login --device` yet"):
        login_with_device_code(Auth())
