import importlib
import importlib.metadata
import json
import os
import re
import threading

import pytest
import requests

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud import rest_client as rest_client_module
from lightning_sdk.lightning_cloud.__version__ import __version__
from lightning_sdk.lightning_cloud.cli_login import LoginError
from lightning_sdk.lightning_cloud.credentials import (
    Credential,
    CredentialKind,
    CredentialSource,
    browser_login,
    logout,
    start_login,
)
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import (
    GridRestClient,
    LightningClient,
    create_swagger_client,
)
from tests.lightning_cloud.utils.fake_platform import FakeBrowser

_MISSING = (
    "We couldn't find any credentials linked to your account. "
    "Please try logging in using the CLI command `lightning login`"
)
_LOGIN_FAILED = "Authentication failed. Please run `lightning login`."
_LOGIN_FIRST = "No Lightning credentials are available. Run `lightning login` first."
_HOUR = 3600
_SWITCH = pytest.mark.parametrize("switch", ["interim", "oidc"])


def _exactly(message):
    return f"^{re.escape(message)}$"


@pytest.fixture(autouse=True)
def isolated_credentials(isolated_login, monkeypatch):
    # Without the fake platform, a login nobody expected fails fast instead of
    # reaching the real Lightning.
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", "http://127.0.0.1:9")
    return Auth.secrets_file


def _set_switch(monkeypatch, switch):
    if switch == "oidc":
        monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    else:
        monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN", raising=False)


def _sent_to_the_api(platform):
    return platform.authorizations_sent("/v1/auth/user")


def test_precedence_is_token_file_then_env_then_saved_login(isolated_credentials, monkeypatch, tmp_path):
    assert env.LIGHTNING_AUTH_TOKEN_FILE == "LIGHTNING_AUTH_TOKEN_FILE"
    isolated_credentials.write_text(
        json.dumps(
            {
                "user_id": "user-1",
                "api_key": "key-saved",
                "auth_token": "sess_saved",
            }
        )
    )
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "sess_env")
    token_file = tmp_path / "token"
    token_file.write_text("  sess_file \n")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))

    source = CredentialSource()
    assert source.header() == "Bearer sess_file"

    token_file.write_text(" \n")
    assert source.header() == "Bearer sess_env"

    token_file.unlink()
    assert source.header() == "Bearer sess_env"

    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN")
    assert source.header() == "Bearer sess_saved"


def test_resolve_names_each_kind_in_precedence_order(platform, browser, monkeypatch, tmp_path):
    made = cli_login.login()
    browser.finish()
    Auth.secrets_file.write_text(json.dumps({"auth_token": "sess_saved"}))
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "sess_env")
    token_file = tmp_path / "token"
    token_file.write_text("lit_w_file")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))
    source = CredentialSource()

    assert source.resolve() == Credential(CredentialKind.TOKEN_FILE, "lit_w_file")
    token_file.unlink()
    assert source.resolve() == Credential(CredentialKind.ENV_TOKEN, "sess_env")
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN")
    assert source.resolve() == Credential(CredentialKind.LOGIN, made.access_token)
    cli_login._forget()
    assert source.resolve() == Credential(CredentialKind.SESSION, "sess_saved")
    assert "sess_saved" not in repr(source.resolve())


def test_token_file_is_reread_between_requests(isolated_credentials, monkeypatch, tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("sess_one\n")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])
        return "ok"

    client = GridRestClient(api_client=_Api(request), with_auth=True)
    client.api_client.request("GET", "http://example")
    token_file.write_text("sess_two")
    client.api_client.request("GET", "http://example")
    assert seen == ["Bearer sess_one", "Bearer sess_two"]


def test_an_unreadable_token_file_is_named_wherever_a_credential_is_read(isolated_credentials, monkeypatch, tmp_path):
    isolated_credentials.write_text(json.dumps({"auth_token": "sess_saved"}))
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(tmp_path))
    named = re.escape(f"{env.LIGHTNING_AUTH_TOKEN_FILE} names {tmp_path}, which can't be read")
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers)
        return "ok"

    with pytest.raises(LoginError, match=named):
        CredentialSource().resolve()
    with pytest.raises(LoginError, match=named):
        Auth().get_auth_header()
    with pytest.raises(LoginError, match=named):
        GridRestClient(api_client=_Api(request), with_auth=True).api_client.request("GET", "http://example")
    assert seen == []


@_SWITCH
def test_a_saved_login_is_bearer_not_basic_in_either_switch_state(platform, isolated_credentials, monkeypatch, switch):
    _set_switch(monkeypatch, switch)
    session = platform.mint_session("user-1")
    isolated_credentials.write_text(json.dumps({"user_id": "user-1", "api_key": "key-1", "auth_token": session}))
    monkeypatch.setenv("LIGHTNING_USER_ID", "user-1")
    monkeypatch.setenv("LIGHTNING_API_KEY", "key-1")

    assert LightningClient().auth_service_get_user().id == "user-1"
    assert Auth().create_api_client().default_headers["Authorization"] == f"Bearer {session}"
    headers = [
        *_sent_to_the_api(platform),
        Auth().authenticate(),
        Auth().auth_header,
        Auth().get_auth_header(),
    ]
    assert all(header.startswith("Bearer ") for header in headers), headers
    assert _sent_to_the_api(platform) == [f"Bearer {session}"]


@pytest.mark.parametrize("user_id", ["user-1", None])
@_SWITCH
def test_an_env_api_key_and_a_saved_api_key_are_never_sent(
    platform, isolated_credentials, monkeypatch, switch, user_id
):
    _set_switch(monkeypatch, switch)
    isolated_credentials.write_text(json.dumps({"user_id": "saved-user", "api_key": "key-saved"}))
    if user_id is None:
        monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    else:
        monkeypatch.setenv("LIGHTNING_USER_ID", f" {user_id} ")
    monkeypatch.setenv("LIGHTNING_API_KEY", " key-env\n")

    assert CredentialSource().resolve() is None
    with browser_login(False):
        with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
            LightningClient().auth_service_get_user()
        with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
            Auth().authenticate()
    with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
        _ = Auth().auth_header
    assert platform.requests == []


@_SWITCH
def test_with_no_credential_the_source_logs_in_once_with_the_login_the_switch_selects(
    platform, browser, monkeypatch, switch
):
    _set_switch(monkeypatch, switch)
    source = CredentialSource()

    first = source.header()
    browser.finish()

    assert source.header() == first
    if switch == "oidc":
        assert first == f"Bearer {cli_login.token(min_remaining=0)}"
        assert (len(platform.authorizations), len(platform.sign_ins)) == (1, 0)
    else:
        assert first == f"Bearer {json.loads(Auth.secrets_file.read_text())['auth_token']}"
        assert (len(platform.authorizations), len(platform.sign_ins)) == (0, 1)
        assert not [path for _, path, _ in platform.requests if path.startswith("/oidc/")]


@_SWITCH
def test_a_token_login_then_a_browser_login_as_another_user_sends_the_second_users_token(platform, monkeypatch, switch):
    platform.token_keys["key-a"] = "user-a"
    Auth().token_login("key-a")
    assert LightningClient().auth_service_get_user().id == "user-a"
    first = json.loads(Auth.secrets_file.read_text())["auth_token"]

    _set_switch(monkeypatch, switch)
    browser = FakeBrowser(platform, user="user-b")
    monkeypatch.setattr("webbrowser.open", browser.open)
    start_login()
    browser.finish()

    assert LightningClient().auth_service_get_user().id == "user-b"
    assert not platform.accepts(first)


def test_a_later_login_replaces_the_earlier_one_and_the_next_request_sends_it(isolated_credentials, platform, browser):
    Auth().save(auth_token=platform.mint_session("user-a"))
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])

    Auth()._run_server()
    GridRestClient(api_client=_Api(request), with_auth=True).api_client.request("GET", "http://example")
    saved = json.loads(isolated_credentials.read_text())["auth_token"]
    assert seen == [f"Bearer {saved}"]
    assert platform.accepts(saved)


@_SWITCH
def test_a_session_saved_by_the_stable_sdk_still_sends_bearer(isolated_credentials, monkeypatch, switch):
    _set_switch(monkeypatch, switch)
    isolated_credentials.write_text(json.dumps({"user_id": "user-1", "api_key": "", "auth_token": "sess_interim"}))
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])

    GridRestClient(api_client=_Api(request), with_auth=True).api_client.request("GET", "http://example")
    assert seen == ["Bearer sess_interim"]


@_SWITCH
def test_a_saved_new_login_is_sent_whatever_the_switch_says(platform, browser, monkeypatch, switch):
    made = cli_login.login()
    _set_switch(monkeypatch, switch)

    assert LightningClient().auth_service_get_user().id == "user-1"
    assert _sent_to_the_api(platform) == [f"Bearer {made.access_token}"]


def test_an_expired_session_gives_one_run_lightning_login_message_without_a_loop(platform, isolated_credentials):
    session = platform.mint_session("user-1")
    isolated_credentials.write_text(json.dumps({"auth_token": session}))
    platform.logout(f"Bearer {session}")

    with pytest.raises(ConnectionError) as refused:
        LightningClient().auth_service_get_user()

    assert str(refused.value) == _LOGIN_FAILED
    assert len(_sent_to_the_api(platform)) == 1


def test_requests_keep_working_across_access_token_expiry_with_one_refresh_each(platform, browser, clock):
    cli_login.login()
    client = GridRestClient()

    for _ in range(3):
        assert client.auth_service_get_user().id == "user-1"
    assert platform.refreshes() == []

    clock.advance(_HOUR - 100)
    for _ in range(3):
        assert client.auth_service_get_user().id == "user-1"
    assert len(platform.refreshes()) == 1

    clock.advance(_HOUR)
    for _ in range(3):
        assert client.auth_service_get_user().id == "user-1"
    assert len(platform.refreshes()) == 2
    assert platform.reuse_events == []


def test_an_access_token_the_server_refuses_is_refreshed_and_the_request_retried_once(platform, browser):
    cli_login.login()
    client = GridRestClient()
    platform.expire_access_tokens()

    assert client.auth_service_get_user().id == "user-1"
    assert len(platform.refreshes()) == 1


def _one_client_two_threads(platform, monkeypatch, other_thread_token):
    """A request whose 401 arrives after another thread used the same client."""
    other = []
    client = None

    def request(method, url, headers=None, **kwargs):
        response = requests.get(
            f"{platform.url}/v1/auth/user",
            headers={"Authorization": headers["Authorization"]},
            timeout=10,
        )
        if response.status_code == 401 and threading.current_thread() is threading.main_thread() and not other:
            with monkeypatch.context() as patch:
                if other_thread_token is not None:
                    patch.setenv("LIGHTNING_AUTH_TOKEN", other_thread_token)
                thread = threading.Thread(
                    target=lambda: other.append(client.api_client.request("GET", "http://example"))
                )
                thread.start()
                thread.join(timeout=10)
        if response.status_code == 401:
            raise ApiException(status=401)
        return response.json()["id"]

    client = GridRestClient(api_client=_Api(request), with_auth=True)
    return client, other


def test_a_refresh_takes_the_token_its_request_sent_after_another_thread_read_another_kind(
    platform, browser, monkeypatch
):
    cli_login.login()
    platform.expire_access_tokens()
    client, other = _one_client_two_threads(platform, monkeypatch, platform.mint_session("user-2"))

    assert client.api_client.request("GET", "http://example") == "user-1"
    assert other == ["user-2"]
    assert len(platform.refreshes()) == 1


def test_a_refresh_after_another_thread_refreshed_the_same_login_does_not_refresh_again(platform, browser, monkeypatch):
    cli_login.login()
    platform.expire_access_tokens()
    client, other = _one_client_two_threads(platform, monkeypatch, None)

    assert client.api_client.request("GET", "http://example") == "user-1"
    assert other == ["user-1"]
    assert len(platform.refreshes()) == 1
    assert platform.reuse_events == []


def test_a_refused_refresh_says_run_lightning_login_once_and_forgets_the_login(platform, browser, clock):
    cli_login.login()
    client = GridRestClient()
    platform.blocked = True
    clock.advance(_HOUR)

    with pytest.raises(LoginError) as refused:
        client.auth_service_get_user()
    assert str(refused.value) == "Your login has expired or was revoked. Run `lightning login`."

    with pytest.raises(ValueError, match=_exactly(_MISSING)):
        client.auth_service_get_user()
    assert len(platform.authorizations) == 1
    assert len(platform.refreshes()) == 1
    assert cli_login.current_login() is None


def test_a_network_error_while_refreshing_keeps_the_unexpired_token(platform, browser, clock, monkeypatch):
    made = cli_login.login()
    client = GridRestClient()
    clock.advance(_HOUR - 100)
    real_post = requests.post

    def unreachable(url, *args, **kwargs):
        if url.endswith("/oidc/token"):
            raise requests.ConnectionError("network down")
        return real_post(url, *args, **kwargs)

    monkeypatch.setattr(requests, "post", unreachable)
    assert client.auth_service_get_user().id == "user-1"
    assert cli_login.token(min_remaining=0) == made.access_token


def test_a_5xx_while_refreshing_keeps_the_unexpired_token(platform, browser, clock, monkeypatch):
    made = cli_login.login()
    client = GridRestClient()
    clock.advance(_HOUR - 100)

    def unavailable(form):
        return 503, {"error": "temporarily_unavailable"}

    monkeypatch.setattr(platform, "token", unavailable)
    assert client.auth_service_get_user().id == "user-1"
    assert len(platform.refreshes()) == 1
    assert cli_login.token(min_remaining=0) == made.access_token


def test_a_401_on_an_explicit_authorization_does_not_refresh_the_login(platform, browser):
    cli_login.login()
    client = GridRestClient()
    assert client.auth_service_get_user().id == "user-1"

    with pytest.raises(ConnectionError):
        client.api_client.call_api(
            "/v1/auth/user",
            "GET",
            header_params={"Authorization": "Bearer someone-else"},
            response_type="V1GetUserResponse",
        )
    assert platform.refreshes() == []


def test_a_login_for_another_url_is_never_sent(platform, browser, monkeypatch):
    cli_login.login()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", "https://other.example")

    def request(method, url, headers=None, **kwargs):
        raise AssertionError("no request is expected")

    client = GridRestClient(api_client=_Api(request), with_auth=True)
    with browser_login(False), pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
        client.api_client.request("GET", "http://example")


def test_with_browser_login_off_a_request_says_run_lightning_login_first():
    def request(method, url, headers=None, **kwargs):
        raise AssertionError("no request is expected")

    client = GridRestClient(api_client=_Api(request), with_auth=True)
    with browser_login(False):
        with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
            client.api_client.request("GET", "http://example")
        with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
            Auth().authenticate()


def test_browser_login_off_holds_for_an_auth_subclass_that_would_log_in():
    started = []

    class LogsIn(Auth):
        def _run_server(self):
            started.append(1)

    with browser_login(False), pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
        LogsIn().authenticate()
    assert started == []


def test_auth_header_never_opens_a_browser():
    with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
        _ = Auth().auth_header


def test_login_that_saves_nothing_raises_the_login_message(monkeypatch):
    started = []

    def run_server(self):
        started.append(1)

    monkeypatch.setattr(Auth, "_run_server", run_server)
    source = CredentialSource()
    with pytest.raises(ValueError, match=_exactly(_MISSING)):
        source.header()
    with pytest.raises(ValueError, match=_exactly(_MISSING)):
        source.header()
    assert started == [1]


def test_a_login_turned_off_where_it_starts_says_so_on_every_request(monkeypatch):
    def refuse(self):
        raise ValueError(_LOGIN_FIRST)

    monkeypatch.setattr(Auth, "_run_server", refuse)
    source = CredentialSource()
    for _ in range(2):
        with pytest.raises(ValueError, match=_exactly(_LOGIN_FIRST)):
            source.header()


def test_token_file_env_and_session_cannot_refresh(isolated_credentials, monkeypatch, tmp_path):
    isolated_credentials.write_text(json.dumps({"auth_token": "sess_saved"}))
    source = CredentialSource()
    assert source.refresh("sess_saved") is False
    assert source.refresh("Bearer sess_saved") is False

    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "sess_env")
    assert source.refresh("sess_env") is False
    assert source.refresh("Bearer sess_env") is False

    token_file = tmp_path / "token"
    token_file.write_text("lit_w_file")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))
    assert source.refresh("lit_w_file") is False
    assert source.refresh("Bearer lit_w_file") is False


def test_a_token_file_rotated_since_the_refused_request_counts_as_refreshed(monkeypatch, tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("lit_w_old")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])
        if len(seen) == 1:
            token_file.write_text("lit_w_new")
            raise ApiException(status=401)
        return "ok"

    client = GridRestClient(api_client=_Api(request), with_auth=True)
    assert client.api_client.request("GET", "http://example") == "ok"
    assert seen == ["Bearer lit_w_old", "Bearer lit_w_new"]


def test_retries_once_when_refresh_succeeds(monkeypatch):
    source = _Refreshable(["old", "new"])
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])
        if len(seen) == 1:
            raise ApiException(status=401)
        return "ok"

    monkeypatch.setattr(rest_client_module, "CredentialSource", lambda: source)
    client = GridRestClient(api_client=_Api(request), with_auth=True)
    assert client.api_client.request("GET", "http://example") == "ok"
    assert seen == ["Bearer old", "Bearer new"]
    assert source.refused == ["Bearer old"]


def test_second_401_after_refresh_raises_once(monkeypatch):
    source = _Refreshable(["same", "same"])
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])
        raise ApiException(status=401)

    monkeypatch.setattr(rest_client_module, "CredentialSource", lambda: source)
    client = GridRestClient(api_client=_Api(request), with_auth=True)
    with pytest.raises(ConnectionError) as exc:
        client.api_client.request("GET", "http://example")
    assert str(exc.value) == _LOGIN_FAILED
    assert len(seen) == 2
    assert source.refused == ["Bearer same"]


def test_non_refreshable_source_raises_on_the_first_401(monkeypatch):
    source = _Static()
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(1)
        raise ApiException(status=401)

    monkeypatch.setattr(rest_client_module, "CredentialSource", lambda: source)
    client = GridRestClient(api_client=_Api(request), with_auth=True)
    with pytest.raises(ConnectionError) as exc:
        client.api_client.request("GET", "http://example")
    assert str(exc.value) == _LOGIN_FAILED
    assert seen == [1]
    assert source.refused == ["Bearer static"]


def test_non_401_is_unchanged(monkeypatch):
    source = _Static()

    def request(method, url, headers=None, **kwargs):
        raise ApiException(status=503)

    monkeypatch.setattr(rest_client_module, "CredentialSource", lambda: source)
    client = GridRestClient(api_client=_Api(request), with_auth=True)
    with pytest.raises(ApiException) as exc:
        client.api_client.request("GET", "http://example")
    assert exc.value.status == 503
    assert source.refused == []


def test_explicit_authorization_is_left_in_place(monkeypatch):
    source = _Static()
    caller_headers = {"Authorization": "Bearer explicit", "Accept": "text/plain"}

    def request(method, url, headers=None, **kwargs):
        return dict(headers)

    monkeypatch.setattr(rest_client_module, "CredentialSource", lambda: source)
    client = GridRestClient(api_client=_Api(request), with_auth=True)
    sent = client.api_client.request("GET", "http://example", headers=caller_headers)
    assert sent["Authorization"] == "Bearer explicit"
    assert sent["Accept"] == "text/plain"
    assert caller_headers == {
        "Authorization": "Bearer explicit",
        "Accept": "text/plain",
    }
    assert source.headers == 0


def test_without_auth_keeps_the_401_wrapper():
    def request(method, url, headers=None, **kwargs):
        assert headers is None or "Authorization" not in headers
        raise ApiException(status=401)

    client = GridRestClient(api_client=_Api(request), with_auth=False)
    with pytest.raises(ConnectionError) as exc:
        client.api_client.request("GET", "http://example")
    assert str(exc.value) == _LOGIN_FAILED


def test_lightning_client_without_auth_does_not_send_authorization(monkeypatch):
    def request(method, url, headers=None, **kwargs):
        return headers

    monkeypatch.setattr(rest_client_module, "create_swagger_client", lambda **kwargs: _Api(request))
    client = LightningClient(retry=False, with_auth=False)
    assert client.api_client.request("GET", "http://example") is None


def test_save_replaces_the_saved_login(isolated_credentials):
    path = isolated_credentials
    auth = Auth()
    auth.save(user_id="user-1", api_key="key-1")
    auth.save(token="ignored", auth_token="sess_1")
    assert json.loads(path.read_text()) == {"user_id": "", "auth_token": "sess_1"}
    assert "api_key" not in path.read_text()
    assert "key-1" not in path.read_text()
    assert not auth.user_id
    assert auth.auth_token == "sess_1"


@pytest.mark.skipif(os.name == "nt", reason="Windows has no POSIX file modes")
def test_saved_login_is_readable_only_by_the_user(isolated_credentials):
    path = isolated_credentials
    Auth().save(auth_token="sess_1")
    assert os.stat(path).st_mode & 0o777 == 0o600
    os.chmod(path, 0o644)
    Auth().save(auth_token="sess_2")
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_save_replaces_a_corrupt_credentials_file(isolated_credentials):
    path = isolated_credentials
    path.write_text('{"auth_token": "sess_1", "trunc')

    Auth().save(auth_token="sess_2")

    assert json.loads(path.read_text())["auth_token"] == "sess_2"


def test_user_agent_names_the_installed_sdk(monkeypatch):
    def version(name):
        if name == "lightning_sdk":
            return "2026.11.3"
        raise importlib.metadata.PackageNotFoundError(name)

    assert _user_agent_with(monkeypatch, version) == "lightning-sdk/2026.11.3"


def test_user_agent_without_the_sdk_names_lightning_cloud(monkeypatch):
    def version(name):
        raise importlib.metadata.PackageNotFoundError(name)

    assert _user_agent_with(monkeypatch, version) == f"lightning-cloud/{__version__}"


def test_every_request_names_the_installed_sdk(platform, browser, monkeypatch):
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    start_login()
    LightningClient().auth_service_get_user()
    monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN")
    start_login()
    browser.finish()
    LightningClient().auth_service_get_user()
    logout()

    browser_pages = {("GET", "/oidc/authorize"), ("GET", "/sign-in")}
    sent = {(method, path): headers.get("User-Agent") for method, path, headers in platform.requests}
    assert set(sent) - browser_pages == {
        ("POST", "/oidc/token"),
        ("POST", "/oidc/revoke"),
        ("HEAD", "/sign-in"),
        ("GET", "/v1/auth/user"),
        ("POST", "/v1/auth/logout"),
    }
    assert {sent[request] for request in set(sent) - browser_pages} == {
        f"lightning-sdk/{importlib.metadata.version('lightning_sdk')}"
    }


def _user_agent_with(monkeypatch, version):
    with monkeypatch.context() as patch:
        patch.setattr(importlib.metadata, "version", version)
        importlib.reload(env)
        try:
            api = create_swagger_client(with_auth=True)
        finally:
            patch.undo()
            importlib.reload(env)
    assert "Authorization" not in api.default_headers
    return api.user_agent


class _Api:
    def __init__(self, request):
        self.request = request


class _Refreshable(CredentialSource):
    def __init__(self, tokens):
        super().__init__()
        self.tokens = list(tokens)
        self.refused = []
        self._index = 0

    def header(self):
        token = self.tokens[min(self._index, len(self.tokens) - 1)]
        return f"Bearer {token}"

    def refresh(self, token):
        self.refused.append(token)
        self._index += 1
        return True


class _Static(CredentialSource):
    def __init__(self):
        super().__init__()
        self.refused = []
        self.headers = 0

    def header(self):
        self.headers += 1
        return "Bearer static"

    def refresh(self, token):
        self.refused.append(token)
        return False
