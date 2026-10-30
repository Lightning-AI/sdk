import base64
import hashlib
import json
from unittest.mock import MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import rich_click as click

from lightning_sdk.cli.legacy.deploy._auth import _AuthLitServe, _AuthMode
from lightning_sdk.cli.utils.auth import (
    browser_authentication,
    login_with_pasted_code,
    logout_session,
    require_auth_header,
)
from lightning_sdk.lightning_cloud.login import Auth


def _response(status_code: int, body=None) -> MagicMock:
    response = MagicMock(status_code=status_code, ok=status_code < 400)
    response.json.return_value = body
    return response


def _login_env(monkeypatch, tmp_path):
    """Point credentials at tmp_path and return the secrets file."""
    secrets_file = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets_file)
    for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN", "LIGHTNING_DEPLOYMENT_ID"):
        monkeypatch.delenv(key, raising=False)
    return secrets_file


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _capture_browser_login(monkeypatch, tmp_path, token_response) -> dict:
    """Run the loopback login with a fake server and browser; return what was captured."""
    captured: dict = {"secrets_file": _login_env(monkeypatch, tmp_path)}

    class FakeServer:
        def __init__(self, config) -> None:
            captured["config"] = config
            captured["route"] = next(r for r in config.app.routes if getattr(r, "path", None) == "/callback")

        def run(self) -> None:
            captured["run"](captured["route"].endpoint)

    post = MagicMock(side_effect=token_response)
    monkeypatch.setattr("lightning_sdk.cli.utils.auth._generate_state", lambda: "fixed-state")
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.head", MagicMock())
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.post", post)
    monkeypatch.setattr("webbrowser.open", lambda url: captured.setdefault("auth_url", url) and True)
    monkeypatch.setattr("uvicorn.Server", FakeServer)
    captured["post"] = post
    return captured


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


def test_login_with_browser_exchanges_the_code_with_pkce_on_loopback(monkeypatch, tmp_path) -> None:
    """The callback trades the code and the verifier matching the sent challenge for a session."""
    from lightning_sdk.lightning_cloud.login import AuthServer

    captured = _capture_browser_login(
        monkeypatch, tmp_path, [_response(200, {"access_token": "sess_user-1.secret", "token_type": "Bearer"})]
    )
    captured["run"] = lambda endpoint: captured.setdefault("location", endpoint(code="the-code", state="fixed-state"))

    auth = Auth()
    AuthServer().login_with_browser(auth)

    url = urlparse(captured["auth_url"])
    query = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.path == "/oidc/authorize"
    assert query["client_id"] == "lightning-cli"
    assert query["response_type"] == "code"
    assert query["state"] == "fixed-state"
    assert query["code_challenge_method"] == "S256"
    assert query["redirect_uri"] == f"http://127.0.0.1:{captured['config'].port}/callback"
    assert captured["config"].host == "127.0.0.1"

    data = captured["post"].call_args.kwargs["data"]
    assert captured["post"].call_args.args[0].endswith("/oidc/token")
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "the-code"
    assert data["redirect_uri"] == query["redirect_uri"]
    assert _challenge(data["code_verifier"]) == query["code_challenge"]

    assert captured["location"].headers["location"].endswith("/cli-login-successful")
    assert auth.auth_token == "sess_user-1.secret"
    assert json.loads(captured["secrets_file"].read_text())["auth_token"] == "sess_user-1.secret"
    assert (captured["secrets_file"].stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize(
    "params",
    [
        {"code": "the-code", "state": ""},
        {"code": "the-code", "state": "forged-state"},
        {"code": "", "state": "fixed-state", "error": "access_denied"},
        {"code": "", "state": "fixed-state"},
    ],
    ids=["no state", "forged state", "denied", "no code"],
)
def test_login_with_browser_refuses_a_bad_callback_without_exchanging(monkeypatch, tmp_path, params) -> None:
    from lightning_sdk.lightning_cloud.login import AuthServer

    captured = _capture_browser_login(monkeypatch, tmp_path, [])
    captured["run"] = lambda endpoint: captured.setdefault("location", endpoint(**params))

    auth = Auth()
    AuthServer().login_with_browser(auth)

    assert captured["location"].headers["location"].endswith("/cli-login-failed")
    captured["post"].assert_not_called()
    assert not captured["secrets_file"].exists()
    assert not auth.auth_token


def test_login_with_browser_reports_a_refused_exchange(monkeypatch, tmp_path) -> None:
    from lightning_sdk.lightning_cloud.login import AuthServer

    captured = _capture_browser_login(monkeypatch, tmp_path, [_response(400, {"error": "invalid_grant"})])
    captured["run"] = lambda endpoint: captured.setdefault("location", endpoint(code="used", state="fixed-state"))

    AuthServer().login_with_browser(Auth())

    assert captured["location"].headers["location"].endswith("/cli-login-failed")
    assert not captured["secrets_file"].exists()


def test_login_with_browser_without_a_browser_falls_back_to_paste(monkeypatch, tmp_path) -> None:
    from lightning_sdk.lightning_cloud.login import AuthServer

    secrets_file = _login_env(monkeypatch, tmp_path)
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.head", MagicMock())
    monkeypatch.setattr("webbrowser.open", lambda url: False)
    monkeypatch.setattr("uvicorn.Server", lambda config: (_ for _ in ()).throw(AssertionError("server started")))
    monkeypatch.setattr(
        "lightning_sdk.cli.utils.auth.login_with_pasted_code", lambda auth: auth.save(auth_token="sess_x")
    )

    AuthServer().login_with_browser(Auth())

    assert json.loads(secrets_file.read_text())["auth_token"] == "sess_x"


def test_login_with_browser_in_a_deployment_without_a_browser_raises(monkeypatch, tmp_path) -> None:
    from lightning_sdk.lightning_cloud.login import AuthServer

    _login_env(monkeypatch, tmp_path)
    monkeypatch.setenv("LIGHTNING_DEPLOYMENT_ID", "dep")
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.head", MagicMock())
    monkeypatch.setattr("webbrowser.open", lambda url: False)

    with pytest.raises(RuntimeError, match="Include SDK credentials"):
        AuthServer().login_with_browser(Auth())


def _paste_login(monkeypatch, tmp_path, codes: list, responses: list) -> tuple:
    secrets_file = _login_env(monkeypatch, tmp_path)
    post = MagicMock(side_effect=responses)
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.requests.post", post)
    monkeypatch.setattr("lightning_sdk.cli.utils.auth.click.prompt", MagicMock(side_effect=codes))
    return secrets_file, post


def test_login_with_pasted_code_prints_the_authorize_url_and_saves_the_session(monkeypatch, tmp_path, capsys) -> None:
    secrets_file, post = _paste_login(
        monkeypatch, tmp_path, [" the-code \n"], [_response(200, {"access_token": "sess_user-1.secret"})]
    )

    login_with_pasted_code(Auth())

    output = capsys.readouterr().out
    url = next(word for word in output.split() if "/oidc/authorize" in word)
    query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert query["client_id"] == "lightning-cli"
    assert query["redirect_uri"].endswith("/cli-login")
    assert query["code_challenge_method"] == "S256"
    assert "never give it to anyone" in output

    data = post.call_args.kwargs["data"]
    assert data["code"] == "the-code"
    assert data["redirect_uri"] == query["redirect_uri"]
    assert _challenge(data["code_verifier"]) == query["code_challenge"]
    assert json.loads(secrets_file.read_text())["auth_token"] == "sess_user-1.secret"


def test_login_with_pasted_code_prompts_again_on_invalid_grant(monkeypatch, tmp_path) -> None:
    secrets_file, post = _paste_login(
        monkeypatch,
        tmp_path,
        ["typo", "the-code"],
        [_response(400, {"error": "invalid_grant"}), _response(200, {"access_token": "sess_user-1.secret"})],
    )

    login_with_pasted_code(Auth())

    assert [c.kwargs["data"]["code"] for c in post.call_args_list] == ["typo", "the-code"]
    assert json.loads(secrets_file.read_text())["auth_token"] == "sess_user-1.secret"


def test_login_with_pasted_code_gives_up_after_three_bad_codes(monkeypatch, tmp_path) -> None:
    refused = [_response(400, {"error": "invalid_grant"})] * 3
    secrets_file, post = _paste_login(monkeypatch, tmp_path, ["a", "b", "c"], refused)

    with pytest.raises(RuntimeError, match="not accepted"):
        login_with_pasted_code(Auth())

    assert post.call_count == 3
    assert not secrets_file.exists()


def test_login_with_pasted_code_stops_on_any_other_error(monkeypatch, tmp_path) -> None:
    secrets_file, post = _paste_login(monkeypatch, tmp_path, ["a"], [_response(404, {})])

    with pytest.raises(RuntimeError, match="HTTP 404"):
        login_with_pasted_code(Auth())

    assert post.call_count == 1
    assert not secrets_file.exists()
