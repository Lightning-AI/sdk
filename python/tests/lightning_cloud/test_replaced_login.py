import json
import webbrowser

import keyring
import pytest

from lightning_sdk.lightning_cloud import cli_login
from lightning_sdk.lightning_cloud.cli_login import LoginError
from lightning_sdk.lightning_cloud.credentials import start_login
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from tests.lightning_cloud.utils.fake_platform import FakeBrowser

_KINDS = ["interim", "oidc"]


class _Saved:
    """What one login left: the token requests send, and what revokes it."""

    def __init__(self, kind, token, refresh_token=None):
        self.kind = kind
        self.token = token
        self.refresh_token = refresh_token


def _log_in(platform, monkeypatch, kind, user, **browser):
    if kind == "oidc":
        monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    else:
        monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN", raising=False)
    fake = FakeBrowser(platform, user=user, **browser)
    monkeypatch.setattr(webbrowser, "open", fake.open)
    try:
        made = start_login()
    finally:
        fake.finish()
    if kind == "oidc":
        return _Saved(kind, made.access_token, made.refresh_token)
    return _Saved(kind, json.loads(Auth.secrets_file.read_text())["auth_token"])


def _revoked(platform, saved):
    if saved.kind == "oidc":
        return [form["token"] for form in platform.calls_to("/oidc/revoke")] == [saved.refresh_token]
    return platform.logouts() == [saved.token]


@pytest.mark.parametrize("second", _KINDS)
@pytest.mark.parametrize("first", _KINDS)
def test_logging_in_again_revokes_the_login_it_replaced(platform, monkeypatch, first, second):
    old = _log_in(platform, monkeypatch, first, "user-a")
    assert LightningClient().auth_service_get_user().id == "user-a"

    _log_in(platform, monkeypatch, second, "user-b")

    assert LightningClient().auth_service_get_user().id == "user-b"
    assert not platform.accepts(old.token)
    assert _revoked(platform, old)
    if first == "oidc":
        assert not platform.family_active(old.refresh_token)
    if second == "interim":
        assert cli_login.current_login() is None
        assert keyring.get_password("lightning-cli", platform.url) is None
    else:
        assert not Auth.secrets_file.exists()


@pytest.mark.parametrize("second", _KINDS)
@pytest.mark.parametrize("first", _KINDS)
def test_a_login_that_fails_leaves_the_old_login_saved_and_live(platform, monkeypatch, first, second):
    old = _log_in(platform, monkeypatch, first, "user-a")

    with pytest.raises(LoginError, match="didn't match"):
        _log_in(platform, monkeypatch, second, "user-b", state="forged")

    assert LightningClient().auth_service_get_user().id == "user-a"
    assert platform.accepts(old.token)
    assert platform.calls_to("/oidc/revoke") == []
    assert platform.logouts() == []


def test_replacing_a_login_says_when_that_revoke_fails(platform, monkeypatch, capsys):
    old = _log_in(platform, monkeypatch, "oidc", "user-a")
    monkeypatch.setattr(platform, "revoke", lambda *args: (503, {}))

    _log_in(platform, monkeypatch, "oidc", "user-b")

    assert platform.family_active(old.refresh_token)
    assert (
        "The saved login could not be revoked on the server and may work until it expires."
        in capsys.readouterr().err
    )


def test_replacing_a_session_says_when_that_revoke_fails(platform, monkeypatch, capsys):
    session = platform.mint_session("user-a")
    Auth.secrets_file.write_text(json.dumps({"auth_token": session}))
    monkeypatch.setattr(platform, "logout", lambda *args: (503, {}))

    _log_in(platform, monkeypatch, "oidc", "user-b")

    assert platform.accepts(session)
    err = capsys.readouterr().err
    assert "The saved session could not be revoked on the server and may work until it expires." in err
    assert "The saved login could not be revoked" not in err
