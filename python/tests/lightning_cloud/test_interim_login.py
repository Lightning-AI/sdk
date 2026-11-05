import json
import os
import re
import webbrowser
from urllib.parse import parse_qs, urlsplit

import pytest

from lightning_sdk.lightning_cloud import cli_login
from lightning_sdk.lightning_cloud.cli_login import LoginError
from lightning_sdk.lightning_cloud.credentials import (
    CredentialKind,
    CredentialSource,
    LoginUnavailable,
    start_login,
)
from lightning_sdk.lightning_cloud.login import Auth, AuthServer
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, SilentBrowser, raised_within

_ENTRY_POINTS = {
    "start_login": start_login,
    "Auth._run_server": lambda: Auth()._run_server(),
    "Auth.authenticate": lambda: Auth().authenticate(),
    "CredentialSource.header": lambda: CredentialSource().header(),
}


def _saved():
    return json.loads(Auth.secrets_file.read_text()) if Auth.secrets_file.exists() else None


def _oidc_requests(platform):
    return [path for _, path, _ in platform.requests if path.startswith("/oidc/")]


def test_the_interim_login_saves_the_sess_as_auth_token_and_the_next_request_sends_it(platform, browser):
    assert start_login() is None
    browser.finish()

    [sign_in] = platform.sign_ins
    assert re.fullmatch(r"http://localhost:\d+/login-complete\?state=[\w-]+", sign_in["redirectTo"])
    saved = _saved()
    assert saved == {"user_id": "user-1", "auth_token": saved["auth_token"]}
    assert saved["auth_token"].startswith("sess_")
    assert browser.landed == f"{platform.url}/cli-login-successful"
    assert CredentialSource().resolve().kind is CredentialKind.SESSION

    assert LightningClient().auth_service_get_user().id == "user-1"
    assert platform.authorizations_sent("/v1/auth/user") == [f"Bearer {saved['auth_token']}"]
    assert _oidc_requests(platform) == []
    assert cli_login.current_login() is None


@pytest.mark.skipif(os.name == "nt", reason="Windows has no POSIX file modes")
def test_the_interim_login_is_saved_in_a_file_only_the_user_can_read(platform, browser):
    Auth.secrets_file.write_text("{}")
    os.chmod(Auth.secrets_file, 0o644)

    start_login()

    assert os.stat(Auth.secrets_file).st_mode & 0o777 == 0o600


def test_an_interim_callback_whose_state_does_not_match_is_refused_and_saves_nothing(platform, monkeypatch):
    browser = FakeBrowser(platform, state="forged")
    monkeypatch.setattr(webbrowser, "open", browser.open)

    with pytest.raises(LoginError, match="didn't match"):
        start_login()
    browser.finish()

    assert browser.landed == f"{platform.url}/cli-login-failed"
    assert _saved() is None


def test_an_interim_callback_without_a_token_saves_nothing(platform, monkeypatch):
    browser = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", browser.open)
    monkeypatch.setattr(platform, "mint_session", lambda user="user-1": "")

    with pytest.raises(LoginError, match="no token"):
        start_login()
    browser.finish()

    assert browser.landed == f"{platform.url}/cli-login-failed"
    assert _saved() is None


def test_sign_in_params_reach_the_interim_sign_in_url(platform, browser):
    start_login(sign_in_params={"okbhrt": "x334uv8t7v", "litaimodel": "lightning-ai/model"})
    browser.finish()

    [sign_in] = platform.sign_ins
    assert sign_in["okbhrt"] == "x334uv8t7v"
    assert sign_in["litaimodel"] == "lightning-ai/model"
    assert _saved()["auth_token"].startswith("sess_")


def test_a_subclass_that_builds_its_own_sign_in_url_still_gets_its_state_checked(platform, monkeypatch):
    class OwnUrl(AuthServer):
        def get_auth_url(self, port):
            return f"{platform.url}/sign-in?redirectTo=http://localhost:{port}/login-complete&okbhrt=code"

    browser = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", browser.open)

    OwnUrl().login_with_browser(Auth())
    browser.finish()

    [sign_in] = platform.sign_ins
    assert sign_in["okbhrt"] == "code"
    assert "state=" in sign_in["redirectTo"]
    assert _saved()["auth_token"].startswith("sess_")


def test_the_interim_login_never_saves_the_legacy_key_the_callback_carries(platform, browser):
    start_login()
    browser.finish()

    assert "api_key" not in _saved()
    assert "key_legacy" not in Auth.secrets_file.read_text()


def test_an_interim_login_with_no_callback_in_five_minutes_stops(platform, clock, monkeypatch):
    browser = SilentBrowser(clock, 5 * 60 + 1)
    monkeypatch.setattr(webbrowser, "open", browser.open)

    stopped = raised_within(10, start_login)

    assert isinstance(stopped, LoginError)
    assert len(browser.opened) == 1
    assert "5 minutes" in str(stopped)
    assert "`lightning login` again" in str(stopped)
    assert "--no-browser" not in str(stopped)
    assert _saved() is None


def test_the_interim_login_says_so_when_no_browser_opens(platform, monkeypatch):
    monkeypatch.setattr(webbrowser, "open", lambda url, *args, **kwargs: False)

    with pytest.raises(LoginError, match="No browser could be opened"):
        start_login()

    assert _saved() is None


@pytest.mark.parametrize("entry", list(_ENTRY_POINTS))
@pytest.mark.parametrize("switch", [None, "1"])
def test_the_switch_chooses_the_login_every_entry_point_starts(platform, browser, monkeypatch, entry, switch):
    if switch:
        monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", switch)

    _ENTRY_POINTS[entry]()
    browser.finish()

    if switch:
        assert (len(platform.authorizations), platform.sign_ins) == (1, [])
        assert cli_login.current_login() is not None
        assert _saved() is None
    else:
        assert (platform.authorizations, len(platform.sign_ins)) == ([], 1)
        assert _oidc_requests(platform) == []
        assert _saved()["auth_token"].startswith("sess_")


def test_the_switch_is_read_when_each_login_starts(platform, monkeypatch):
    browser = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", browser.open)

    start_login()
    browser.finish()
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    made = start_login()
    browser.finish()

    assert len(platform.sign_ins) == 1
    assert len(platform.authorizations) == 1
    assert cli_login.token(min_remaining=0) == made.access_token


@pytest.mark.parametrize(
    ("options", "named"),
    [
        ({"no_browser": True}, "--no-browser"),
        ({"insecure_storage": True}, "--insecure-storage"),
    ],
)
def test_without_the_switch_an_option_only_the_new_login_has_is_refused(platform, monkeypatch, options, named):
    monkeypatch.setattr(webbrowser, "open", lambda url, *args, **kwargs: pytest.fail("a browser opened"))

    with pytest.raises(LoginUnavailable) as refused:
        start_login(**options)

    assert isinstance(refused.value, ValueError)
    assert named in str(refused.value)
    assert "LIGHTNING_CLI_OIDC_LOGIN" in str(refused.value)
    assert platform.requests == []


def test_with_the_switch_the_new_login_ignores_sign_in_params(platform, browser, _oidc_login):
    made = start_login(sign_in_params={"okbhrt": "code"})

    [consent] = platform.authorizations
    assert "okbhrt" not in consent
    assert made.grant == {"orgs": "all", "permissions": ["read", "write"]}


def test_the_interim_login_url_carries_no_credential(platform, browser):
    start_login()
    browser.finish()

    saved = _saved()["auth_token"]
    for url in browser.visited[:1] + [browser.landed]:
        assert saved not in url
        assert "token=" not in urlsplit(url).query
    assert parse_qs(urlsplit(browser.landed).query) == {}
