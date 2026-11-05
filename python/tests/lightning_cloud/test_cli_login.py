import getpass
import json
import logging
import os
import pathlib
import threading
import webbrowser

import keyring
import pytest
from keyring.backends import fail

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.cli_login import LoginError
from lightning_sdk.lightning_cloud.credentials import CredentialKind, logout
from lightning_sdk.lightning_cloud.login import Auth
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, OtherDevice, SilentBrowser, raised_within
from tests.lightning_cloud.utils.keyrings import MemoryKeyring

_HOUR = 3600


def _keychain_entry(url):
    return keyring.get_password("lightning-cli", url) or ""


def _login_file():
    path = pathlib.Path(env.LIGHTNING_LOGIN_PATH)
    return path.read_text() if path.exists() else ""


def _nothing_saved(url):
    assert cli_login.current_login() is None
    assert _login_file() == ""
    assert _keychain_entry(url) == ""


def _use_browser(monkeypatch, browser):
    monkeypatch.setattr(webbrowser, "open", browser.open)
    return browser


def _paste_codes(monkeypatch, platform, capsys, typed):
    terminal = []

    def read_terminal():
        captured = capsys.readouterr()
        terminal.append(captured.out + captured.err)
        return "".join(terminal)

    device = OtherDevice(platform, read_terminal, typed)
    monkeypatch.setattr(getpass, "getpass", device.getpass)
    return device, read_terminal


def test_browser_login_keeps_the_pair_in_the_keychain_and_out_of_urls_logs_and_terminal(
    platform, browser, capsys, caplog
):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="urllib3")

    made = cli_login.login()
    browser.finish()

    entry = _keychain_entry(platform.url)
    assert made.access_token in entry
    assert made.refresh_token in entry
    assert platform.accepts(made.access_token)
    assert browser.landed == f"{platform.url}/cli-login-successful"
    assert len(platform.authorizations) == 1
    exchange = platform.calls_to("/oidc/token")[0]
    assert exchange["storage"] == "keychain"

    captured = capsys.readouterr()
    sdk_logs = [r.getMessage() for r in caplog.records if r.thread == threading.get_ident()]
    assert sdk_logs
    shown = captured.out + captured.err + "\n".join(sdk_logs) + repr(made) + _login_file()
    for secret in (made.access_token, made.refresh_token, exchange["code"], exchange["code_verifier"]):
        assert secret not in shown
    for url in [*browser.visited, browser.landed]:
        assert made.access_token not in url
        assert made.refresh_token not in url
        assert exchange["code_verifier"] not in url


def test_status_shows_grant_storage_and_expiries_without_tokens(platform, browser, clock):
    cli_login.login()

    status = cli_login.current_login()

    assert status.url == platform.url
    assert status.storage == "keychain"
    assert status.grant == {"orgs": "all", "permissions": ["read", "write"]}
    assert status.access_expires_at == pytest.approx(clock.now + _HOUR)
    assert status.refresh_expires_at == pytest.approx(clock.now + 14 * 24 * _HOUR, abs=1)
    assert not hasattr(status, "access_token")
    assert not hasattr(status, "refresh_token")


def test_the_authorize_url_carries_no_org_or_project_hint(platform, browser):
    cli_login.login()

    consent = platform.authorizations[0]
    assert "orgs_hint" not in consent
    assert "project_hint" not in consent


def test_the_loopback_answers_other_paths_with_404_and_keeps_waiting(platform, monkeypatch):
    browser = _use_browser(monkeypatch, FakeBrowser(platform, stray_paths=["/favicon.ico"]))

    made = cli_login.login()
    browser.finish()

    assert browser.stray_statuses == [404]
    assert platform.accepts(made.access_token)


def test_a_callback_whose_state_does_not_match_is_refused_and_saves_nothing(platform, monkeypatch):
    browser = _use_browser(monkeypatch, FakeBrowser(platform, state="forged"))

    with pytest.raises(LoginError, match="didn't match"):
        cli_login.login()
    browser.finish()

    assert browser.landed == f"{platform.url}/cli-login-failed"
    assert platform.calls_to("/oidc/token") == []
    _nothing_saved(platform.url)


def test_a_denied_login_saves_nothing(platform, monkeypatch):
    browser = _use_browser(monkeypatch, FakeBrowser(platform, deny=True))

    with pytest.raises(LoginError, match="denied"):
        cli_login.login()
    browser.finish()

    assert browser.landed == f"{platform.url}/cli-login-failed"
    assert platform.calls_to("/oidc/token") == []
    _nothing_saved(platform.url)


def test_a_browser_login_with_no_callback_in_five_minutes_stops_and_suggests_no_browser(platform, clock, monkeypatch):
    browser = _use_browser(monkeypatch, SilentBrowser(clock, 5 * 60 + 1))

    stopped = raised_within(10, cli_login.login)

    assert isinstance(stopped, LoginError)
    assert len(browser.opened) == 1
    assert "`lightning login`" in str(stopped)
    assert "--no-browser" in str(stopped)
    assert platform.calls_to("/oidc/token") == []
    _nothing_saved(platform.url)


def test_a_browser_login_answered_within_five_minutes_completes(platform, clock, monkeypatch):
    real = FakeBrowser(platform)

    def open_late(url, *args, **kwargs):
        clock.advance(5 * 60 - 1)
        return real.open(url)

    monkeypatch.setattr(webbrowser, "open", open_late)
    made = cli_login.login()
    real.finish()

    assert platform.accepts(made.access_token)


def test_paste_back_asks_again_after_a_wrong_code(platform, monkeypatch, capsys):
    device, read_terminal = _paste_codes(monkeypatch, platform, capsys, ["wrong", "CODE"])

    made = cli_login.login(no_browser=True)

    assert device.prompts == 2
    assert platform.accepts(made.access_token)
    exchanges = platform.calls_to("/oidc/token")
    assert [form["code"] for form in exchanges] == ["wrong", device.code]
    assert {form["redirect_uri"] for form in exchanges} == {f"{platform.url}/cli-login"}
    terminal = read_terminal()
    assert "never into a website, form, chat or email" in terminal
    assert device.code not in terminal
    assert made.access_token not in terminal


def test_three_wrong_codes_end_the_login(platform, monkeypatch, capsys):
    device, _ = _paste_codes(monkeypatch, platform, capsys, ["one", "two", "three", "CODE"])

    with pytest.raises(LoginError, match="3 tries"):
        cli_login.login(no_browser=True)

    assert device.prompts == 3
    assert len(platform.calls_to("/oidc/token")) == 3
    _nothing_saved(platform.url)


def test_a_browser_that_cannot_open_falls_back_to_paste_back(platform, monkeypatch, capsys):
    monkeypatch.setattr(webbrowser, "open", lambda url, *args, **kwargs: False)
    device, _ = _paste_codes(monkeypatch, platform, capsys, ["CODE"])

    made = cli_login.login()

    assert device.prompts == 1
    assert platform.accepts(made.access_token)


def test_a_deployment_without_a_browser_says_to_include_sdk_credentials(platform, monkeypatch):
    monkeypatch.setattr(webbrowser, "open", lambda url, *args, **kwargs: False)
    monkeypatch.setenv("LIGHTNING_DEPLOYMENT_ID", "the deployment id")

    with pytest.raises(LoginError, match="Include SDK credentials"):
        cli_login.login()


def test_without_a_keychain_login_refuses_and_names_insecure_storage(platform, browser):
    keyring.set_keyring(fail.Keyring())

    with pytest.raises(LoginError, match="--insecure-storage"):
        cli_login.login()

    assert browser.visited == []
    assert platform.calls == []


def test_a_keychain_that_refuses_the_save_revokes_the_new_login_and_keeps_the_old_one(platform, browser):
    old = platform.mint_session("user-1")
    Auth().save(auth_token=old)

    class Refusing(MemoryKeyring):
        def set_password(self, service, username, password):
            raise RuntimeError("locked")

    keyring.set_keyring(Refusing())

    with pytest.raises(LoginError, match="--insecure-storage"):
        cli_login.login()

    [revoked] = platform.calls_to("/oidc/revoke")
    assert not platform.family_active(revoked["token"])
    assert cli_login.current_login() is None
    assert json.loads(Auth.secrets_file.read_text())["auth_token"] == old
    assert platform.session_active(old)
    assert platform.logouts() == []


def test_insecure_storage_keeps_the_login_in_a_file_only_the_user_can_read(platform, browser, clock):
    keyring.set_keyring(fail.Keyring())

    made = cli_login.login(insecure_storage=True)

    assert platform.calls_to("/oidc/token")[0]["storage"] == "file"
    assert platform.family_storage(made.refresh_token) == "file"
    assert made.refresh_expires_at == pytest.approx(clock.now + 7 * 24 * _HOUR, abs=1)
    assert cli_login.token() == made.access_token
    if os.name != "nt":
        assert os.stat(env.LIGHTNING_LOGIN_PATH).st_mode & 0o777 == 0o600


def test_a_new_login_removes_the_interim_credentials(platform, browser):
    Auth.secrets_file.write_text(json.dumps({"auth_token": "sess_legacy"}))

    cli_login.login()

    assert not Auth.secrets_file.exists()


def test_token_with_twenty_minutes_left_refreshes_first_and_survives_a_later_refresh(platform, browser, clock):
    made = cli_login.login()
    clock.advance(_HOUR - 20 * 60)

    printed = cli_login.token()

    assert printed != made.access_token
    assert len(platform.refreshes()) == 1
    assert cli_login.current_login().access_expires_at - clock.now > 50 * 60

    clock.advance(55 * 60)
    later = cli_login.token()
    assert later != printed
    assert len(platform.refreshes()) == 2
    assert platform.accepts(printed)

    assert logout() == ()
    assert not platform.accepts(printed)
    assert not platform.accepts(later)


def test_token_with_enough_time_left_does_not_refresh(platform, browser, clock):
    made = cli_login.login()
    clock.advance(20 * 60)

    assert cli_login.token() == made.access_token
    assert platform.refreshes() == []


def test_token_without_a_login_says_to_log_in(platform):
    with pytest.raises(LoginError, match="lightning login"):
        cli_login.token()


def test_logout_revokes_both_kinds_on_the_server_and_forgets_both_locally(platform, browser):
    made = cli_login.login()
    session = platform.mint_session("user-1")
    Auth.secrets_file.write_text(json.dumps({"auth_token": session}))

    assert logout() == ()

    assert [form["token"] for form in platform.calls_to("/oidc/revoke")] == [made.refresh_token]
    assert platform.logouts() == [session]
    assert not platform.family_active(made.refresh_token)
    assert not platform.accepts(made.access_token)
    assert not platform.accepts(session)
    assert not Auth.secrets_file.exists()
    _nothing_saved(platform.url)


@pytest.mark.parametrize(
    ("refusing", "failed"),
    [("revoke", (CredentialKind.LOGIN,)), ("logout", (CredentialKind.SESSION,))],
)
def test_logout_still_revokes_the_other_kind_and_forgets_both_when_one_revoke_fails(
    platform, browser, monkeypatch, refusing, failed
):
    made = cli_login.login()
    session = platform.mint_session("user-1")
    Auth.secrets_file.write_text(json.dumps({"auth_token": session}))
    monkeypatch.setattr(platform, refusing, lambda *args: (503, {}))

    assert logout() == failed

    assert platform.accepts(session) == (refusing == "logout")
    assert platform.family_active(made.refresh_token) == (refusing == "revoke")
    assert not Auth.secrets_file.exists()
    _nothing_saved(platform.url)


def test_logout_that_cannot_reach_the_server_still_forgets_locally(platform, browser):
    cli_login.login()
    Auth.secrets_file.write_text(json.dumps({"auth_token": "sess_legacy"}))
    platform.stop()

    assert logout() == (CredentialKind.LOGIN, CredentialKind.SESSION)

    assert not Auth.secrets_file.exists()
    _nothing_saved(platform.url)


def test_logout_forgets_a_login_whose_keychain_cannot_be_read(platform, browser):
    cli_login.login()
    path = pathlib.Path(env.LIGHTNING_LOGIN_PATH)
    assert path.is_file()
    keyring.set_keyring(fail.Keyring())

    assert logout() == (CredentialKind.LOGIN,)

    assert not path.exists()
    assert platform.calls_to("/oidc/revoke") == []


def test_logout_with_nothing_saved_revokes_nothing(platform):
    assert logout() == ()
    assert platform.requests == []


def test_every_token_and_revoke_call_names_the_client(platform, browser, clock):
    cli_login.login()
    clock.advance(_HOUR)
    cli_login.token()
    cli_login.login()
    logout()

    paths = [path for path, _, _ in platform.calls]
    assert paths == ["/oidc/token", "/oidc/token", "/oidc/token", "/oidc/revoke", "/oidc/revoke"]
    for _, form, user_agent in platform.calls:
        assert form["client_id"] == "lightning-cli"
        assert user_agent == env.USER_AGENT


def test_a_login_for_another_url_is_ignored(platform, browser, monkeypatch):
    cli_login.login()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", "https://other.example")

    assert cli_login.current_login() is None
    with pytest.raises(LoginError, match="not logged in"):
        cli_login.token()
    assert platform.calls_to("/oidc/token")[1:] == []


def test_a_refused_refresh_forgets_the_login(platform, browser, clock):
    cli_login.login()
    platform.blocked = True
    clock.advance(_HOUR)

    with pytest.raises(LoginError) as refused:
        cli_login.token()

    assert str(refused.value) == "Your login has expired or was revoked. Run `lightning login`."
    _nothing_saved(platform.url)
    with pytest.raises(LoginError, match="not logged in"):
        cli_login.token()
    assert len(platform.refreshes()) == 1


def test_a_refresh_token_used_elsewhere_says_the_login_was_copied(platform, browser, clock):
    made = cli_login.login()
    status, _ = platform.token(
        {
            "client_id": "lightning-cli",
            "grant_type": "refresh_token",
            "refresh_token": made.refresh_token,
        }
    )
    assert status == 200
    clock.advance(_HOUR)

    with pytest.raises(LoginError) as refused:
        cli_login.token()

    assert str(refused.value) == (
        "This login was revoked because a copy of it was used elsewhere. "
        "Run `lightning login` and consider rotating any keys this machine held."
    )
    _nothing_saved(platform.url)


@pytest.mark.parametrize(
    "description",
    ["refresh token was reused", "the login is revoked", "Refresh token was reused; the login is revoked."],
)
def test_only_the_exact_reuse_text_gives_the_reuse_message(platform, browser, clock, monkeypatch, description):
    cli_login.login()
    monkeypatch.setattr(
        platform, "token", lambda form: (400, {"error": "invalid_grant", "error_description": description})
    )
    clock.advance(_HOUR)

    with pytest.raises(LoginError) as refused:
        cli_login.token()

    assert str(refused.value) == "Your login has expired or was revoked. Run `lightning login`."


def test_token_says_so_when_it_cannot_refresh(platform, browser, clock, monkeypatch):
    cli_login.login()
    clock.advance(_HOUR - 20 * 60)
    platform.stop()

    with pytest.raises(LoginError, match="Couldn't refresh"):
        cli_login.token()

    assert cli_login.current_login() is not None


def test_a_save_interrupted_between_keychain_and_login_file_converges(platform, browser, clock, monkeypatch):
    cli_login.login()
    clock.advance(_HOUR)
    real_replace = os.replace

    def crash(source, target):
        raise OSError("disk went away")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="disk went away"):
        cli_login.token()
    monkeypatch.setattr(os, "replace", real_replace)

    printed = cli_login.token()

    assert platform.accepts(printed)
    assert platform.reuse_events == []
    assert platform.family_active(printed)
    assert len(platform.refreshes()) == 2
    assert cli_login.token() == printed
