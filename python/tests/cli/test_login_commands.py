"""Login, logout, auth status and auth token, against the fake platform."""

import getpass
import json
import re
import sys
import threading
import webbrowser
from types import SimpleNamespace

import keyring
import pytest
from click.testing import CliRunner

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.cli.legacy.entrypoint import main_cli as legacy_cli
from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.credentials import CredentialSource, logout
from lightning_sdk.lightning_cloud.login import Auth
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, FakePlatform, OtherDevice
from tests.lightning_cloud.utils.keyrings import MemoryKeyring

_REAL_THREAD = threading.Thread
_NOT_LOGGED_IN = "You are not logged in. Run `lightning login`."


def _text(result) -> str:
    return result.output + (getattr(result, "stderr", None) or "")


def _plain(result) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*m", "", _text(result)).split())


@pytest.fixture()
def isolated(monkeypatch, tmp_path):
    """A private credential store, no ambient token, and real threads for the fake servers."""
    # Assigning, not monkeypatch: restoring the suite's Thread mock after the test
    # makes the timeout timer fail its Thread.__init__ check.
    threading.Thread = _REAL_THREAD
    for name in (
        "LIGHTNING_AUTH_TOKEN",
        "LIGHTNING_AUTH_TOKEN_FILE",
        "LIGHTNING_API_KEY",
        "LIGHTNING_USER_ID",
        "LIGHTNING_CLI_OIDC_LOGIN",
    ):
        monkeypatch.delenv(name, raising=False)
    credentials = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", credentials)
    monkeypatch.setenv("LIGHTNING_CREDENTIAL_PATH", str(credentials))
    login_path = tmp_path / "login.json"
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(login_path))
    monkeypatch.setenv("LIGHTNING_LOGIN_PATH", str(login_path))
    monkeypatch.setattr("lightning_sdk.cli.utils.auth._get_authed_user", lambda: SimpleNamespace(name="ada"))
    cached_lightning_client.cache_clear()
    previous = keyring.get_keyring()
    memory = MemoryKeyring()
    keyring.set_keyring(memory)
    try:
        yield tmp_path
    finally:
        keyring.set_keyring(previous)
        cached_lightning_client.cache_clear()


@pytest.fixture()
def platform(isolated, monkeypatch):
    fake = FakePlatform()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", fake.url)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", fake.url)
    cached_lightning_client.cache_clear()
    yield fake
    fake.stop()


@pytest.fixture()
def browser(platform, monkeypatch):
    fake = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", fake.open)
    yield fake
    fake.finish()


def _invoke(cli, args):
    return CliRunner().invoke(cli, args)


def _saved_session() -> str:
    data = json.loads(Auth.secrets_file.read_text())
    return data["auth_token"]


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
def test_login_uses_the_interim_flow_when_the_switch_is_unset(platform, browser, cli) -> None:
    result = _invoke(cli, ["login"])

    assert result.exit_code == 0, _text(result)
    assert _saved_session().startswith("sess_")
    assert platform.sign_ins
    assert not platform.authorizations
    assert 'Successfully logged in as "ada".' in result.output


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
@pytest.mark.parametrize(
    "args",
    [["--no-browser"], ["--insecure-storage"], ["--org", "acme"], ["--project", "research"]],
)
def test_interim_login_refuses_flags_the_new_login_needs(isolated, cli, args) -> None:
    result = _invoke(cli, ["login", *args])

    assert result.exit_code == 2, _text(result)
    assert "LIGHTNING_CLI_OIDC_LOGIN" in _text(result)
    assert not Auth.secrets_file.exists()


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
def test_login_refuses_a_token_file_and_an_environment_token(isolated, monkeypatch, cli) -> None:
    token_file = isolated / "token"
    token_file.write_text("from-file")
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN_FILE", str(token_file))
    refused = _invoke(cli, ["login"])
    assert refused.exit_code == 2
    assert "LIGHTNING_AUTH_TOKEN_FILE" in _text(refused)

    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN_FILE")
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "from-env")
    refused = _invoke(cli, ["login"])
    assert refused.exit_code == 2
    assert "LIGHTNING_AUTH_TOKEN" in _text(refused)
    assert not Auth.secrets_file.exists()


_LOGIN_NOT_REQUIRED = '"lightning login" is not required within a Studio or when credentials are set in the environment'


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
def test_with_the_switch_unset_login_says_an_api_key_needs_no_login(platform, browser, monkeypatch, cli) -> None:
    monkeypatch.setenv("LIGHTNING_USER_ID", "user-1")
    monkeypatch.setenv("LIGHTNING_API_KEY", "key-1")

    result = _invoke(cli, ["login"])

    assert result.exit_code == 0, _text(result)
    assert result.stdout == _LOGIN_NOT_REQUIRED + "\n"
    assert "Successfully logged in" not in _text(result)
    assert not platform.sign_ins
    assert not platform.authorizations
    assert not Auth.secrets_file.exists()


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
def test_with_the_switch_set_login_warns_that_an_api_key_is_ignored_and_continues(
    platform, browser, monkeypatch, cli
) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    monkeypatch.setenv("LIGHTNING_API_KEY", "lit_sa_ignored")

    result = _invoke(cli, ["login"])

    assert result.exit_code == 0, _text(result)
    assert "LIGHTNING_API_KEY is ignored until service accounts" in result.stderr
    assert CredentialSource().resolve().token.startswith("lit_ua_")
    assert "lit_sa_ignored" not in _text(result)


def test_login_keeps_the_previous_session_until_the_new_one_is_saved(platform, browser) -> None:
    previous = platform.mint_session("user-1")
    Auth().save(auth_token=previous)

    result = _invoke(main_cli, ["login"])

    assert result.exit_code == 0, _text(result)
    assert previous in platform.logouts()
    assert _saved_session() != previous
    assert _saved_session().startswith("sess_")


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
def test_login_with_the_switch_uses_the_new_login(platform, browser, monkeypatch, cli) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")

    result = _invoke(cli, ["login"])

    assert result.exit_code == 0, _text(result)
    assert platform.authorizations
    assert CredentialSource().resolve().token.startswith("lit_ua_")
    assert not platform.sign_ins


def test_insecure_storage_warns_and_names_the_login_file(platform, browser, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")

    result = _invoke(main_cli, ["login", "--insecure-storage"])

    assert result.exit_code == 0, _text(result)
    assert env.LIGHTNING_LOGIN_PATH in _text(result)
    assert "file" in _text(result)
    assert CredentialSource().resolve().kind.value == "login"


@pytest.mark.parametrize("args", [["--org", "acme"], ["--no-browser", "--org", "acme"]])
def test_login_names_a_grant_that_reaches_further_than_the_hints(platform, browser, monkeypatch, args) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    if "--no-browser" in args:

        def read_terminal():
            sys.stderr.flush()
            captured = getattr(sys.stderr, "buffer", sys.stderr)
            raw = captured.getvalue() if hasattr(captured, "getvalue") else ""
            return raw.decode() if isinstance(raw, bytes) else raw

        device = OtherDevice(platform, read_terminal, ["CODE"])
        monkeypatch.setattr(getpass, "getpass", device.getpass)

    result = _invoke(main_cli, ["login", *args])

    assert result.exit_code == 0, _text(result)
    assert "reaches more than you asked for" in _text(result)
    assert '"orgs": "all"' in _text(result)


def test_login_stays_quiet_when_the_grant_matches_the_hints(platform, browser, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    original = platform._issue

    def matching(family):
        body = original(family)
        body["lightning_grant"] = {"orgs": [{"org": "acme", "projects": ["research"]}], "permissions": ["read"]}
        return body

    platform._issue = matching

    result = _invoke(main_cli, ["login", "--org", "acme", "--project", "research"])

    assert result.exit_code == 0, _text(result)
    assert "reaches more than you asked for" not in _text(result)


def test_a_studio_without_credentials_still_refuses_to_log_in(monkeypatch) -> None:
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN_FILE", raising=False)
    monkeypatch.setenv("LIGHTNING_INTERACTIVE", "true")
    monkeypatch.setenv("LIGHTNING_CLOUD_SPACE_ID", "studio-1")

    result = _invoke(main_cli, ["login"])

    assert result.exit_code != 0
    assert "Unable to login within a Studio" in str(result.exception)


@pytest.mark.parametrize("cli", [main_cli, legacy_cli])
def test_logout_revokes_both_kinds_and_names_the_one_the_server_refused(platform, browser, monkeypatch, cli) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    assert _invoke(cli, ["login"]).exit_code == 0
    session = platform.mint_session("user-1")
    Auth().save(auth_token=session)
    platform.revoke = lambda _form: (500, {"error": "unavailable"})

    result = _invoke(cli, ["logout"])

    text = _text(result)
    assert result.exit_code == 0, text
    assert "Logged out on this machine." in text
    assert "could not be revoked on the server" in text
    assert "may work until it expires" in text
    assert "Logout failed" not in text
    assert not platform.session_active(session)
    assert CredentialSource().resolve() is None


def test_auth_status_names_each_source_and_never_a_token(platform, browser, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    assert _invoke(main_cli, ["login"]).exit_code == 0
    login_token = CredentialSource().resolve().token

    logged_in = _invoke(main_cli, ["auth", "status"])
    assert logged_in.exit_code == 0, _text(logged_in)
    assert "login (keychain)" in _text(logged_in)
    assert "all" in _text(logged_in)
    assert login_token not in _text(logged_in)
    assert f"Bearer {login_token}" in platform.authorizations_sent("/v1/auth/user")

    logout()
    token_path = tmp_path / "workload"
    token_path.write_text("file-token")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN_FILE", "workload")
    from_file = _invoke(main_cli, ["auth", "status"])
    assert "token file workload" in _text(from_file)
    assert "not known locally" in _text(from_file)
    assert "file-token" not in _text(from_file)
    assert "not logged in" not in _text(from_file).lower()

    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN_FILE")
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "env-token")
    from_env = _invoke(main_cli, ["auth", "status"])
    assert "LIGHTNING_AUTH_TOKEN" in _text(from_env)
    assert "not known locally" in _text(from_env)
    assert "env-token" not in _text(from_env)
    assert "not logged in" not in _text(from_env).lower()

    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN")
    Auth().save(auth_token="sess_saved")
    from_session = _invoke(main_cli, ["auth", "status"])
    assert "interim session login" in _text(from_session)
    assert "not known locally" in _text(from_session)
    assert "sess_saved" not in _text(from_session)

    Auth.secrets_file.unlink()
    missing = _invoke(main_cli, ["auth", "status"])
    assert missing.exit_code != 0
    assert _NOT_LOGGED_IN in _text(missing)

    monkeypatch.setenv("LIGHTNING_USER_ID", "user-1")
    monkeypatch.setenv("LIGHTNING_API_KEY", "key-1")
    monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN", raising=False)
    legacy = _invoke(main_cli, ["auth", "status"])
    shown = _plain(legacy)
    assert legacy.exit_code == 0, _text(legacy)
    assert "LIGHTNING_API_KEY (legacy key, until the new login is switched on)" in shown
    assert "Orgs" in shown
    assert "Teamspaces" in shown
    assert "Permissions" in shown
    assert "Expiry" in shown
    assert shown.count("not known locally") == 4
    assert "key-1" not in shown

    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    hidden = _invoke(main_cli, ["auth", "status"])
    assert hidden.exit_code != 0
    assert _NOT_LOGGED_IN in _text(hidden)
    assert "key-1" not in _text(hidden)


def test_auth_token_prints_what_requests_send_and_refuses_a_short_login(platform, monkeypatch) -> None:
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "env-token")
    printed = _invoke(main_cli, ["auth", "token"])
    assert printed.exit_code == 0, _text(printed)
    assert printed.stdout == "env-token\n"
    assert "LIGHTNING_AUTH_TOKEN" in printed.stderr
    assert "what requests send" in printed.stderr

    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN")
    monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN", raising=False)
    monkeypatch.setenv("LIGHTNING_USER_ID", "user-1")
    monkeypatch.setenv("LIGHTNING_API_KEY", "lit_sa_secret")
    refused = _invoke(main_cli, ["auth", "token"])
    assert refused.exit_code != 0
    assert refused.stdout == ""
    assert "lit_sa_secret" not in _text(refused)
    assert "A legacy key is never printed. Run `lightning login`." in _text(refused)

    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    hidden = _invoke(main_cli, ["auth", "token"])
    assert hidden.exit_code != 0
    assert hidden.stdout == ""
    assert "lit_sa_secret" not in _text(hidden)
    assert _NOT_LOGGED_IN in _text(hidden)

    monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN")
    monkeypatch.delenv("LIGHTNING_API_KEY")
    monkeypatch.delenv("LIGHTNING_USER_ID")
    Auth().save(auth_token="sess_saved")
    session = _invoke(main_cli, ["auth", "token"])
    assert session.stdout == "sess_saved\n"
    assert "interim session login" in session.stderr
    assert "what requests send" in session.stderr


def test_auth_token_refuses_a_short_lived_login_without_a_fallback(monkeypatch, tmp_path) -> None:
    threading.Thread = _REAL_THREAD
    for name in ("LIGHTNING_AUTH_TOKEN", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    credentials = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", credentials)
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(tmp_path / "login.json"))
    previous = keyring.get_keyring()
    keyring.set_keyring(MemoryKeyring())
    fake = FakePlatform(access_ttl=60)
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", fake.url)
    browser = FakeBrowser(fake)
    monkeypatch.setattr(webbrowser, "open", browser.open)
    monkeypatch.setattr("lightning_sdk.cli.utils.auth._get_authed_user", lambda: SimpleNamespace(name="ada"))
    try:
        assert _invoke(main_cli, ["login"]).exit_code == 0
        access = CredentialSource().resolve().token
        original = fake.token

        def refuse_refresh(form):
            if form.get("grant_type") == "refresh_token":
                return 500, {"error": "unavailable"}
            return original(form)

        fake.token = refuse_refresh
        result = _invoke(main_cli, ["auth", "token"])
        assert result.exit_code != 0
        assert "Couldn't refresh" in _text(result)
        assert access not in _text(result)
    finally:
        browser.finish()
        fake.stop()
        keyring.set_keyring(previous)
