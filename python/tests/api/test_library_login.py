"""LitAI and LitServe stay on the credential source."""

import threading
import webbrowser

import click
import keyring
import pytest

from lightning_sdk.api.llm_api import authenticate as litai_authenticate
from lightning_sdk.cli.legacy.deploy._auth import _AuthMode
from lightning_sdk.cli.legacy.deploy._auth import authenticate as litserve_authenticate
from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.login import Auth
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, FakePlatform
from tests.lightning_cloud.utils.keyrings import MemoryKeyring

_REAL_THREAD = threading.Thread


def _clear_credentials(monkeypatch, tmp_path):
    threading.Thread = _REAL_THREAD
    for name in ("LIGHTNING_AUTH_TOKEN", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN_FILE"):
        monkeypatch.delenv(name, raising=False)
    secrets = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", secrets)
    return secrets


def test_litserve_does_not_open_a_browser_when_nothing_is_saved(monkeypatch, tmp_path):
    _clear_credentials(monkeypatch, tmp_path)

    def opened(*_args, **_kwargs):
        raise AssertionError("opened a browser")

    monkeypatch.setattr(webbrowser, "open", opened)

    with pytest.raises(click.UsageError, match="No Lightning credentials are available. Run `lightning login` first."):
        litserve_authenticate(_AuthMode.DEPLOY)


def test_litserve_uses_an_existing_credential_without_a_browser(monkeypatch):
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "env-token")
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda *_args, **_kwargs: opened.append(True))

    litserve_authenticate(_AuthMode.DEPLOY)

    assert opened == []


def test_litai_logs_in_with_the_new_login(monkeypatch, tmp_path):
    _clear_credentials(monkeypatch, tmp_path)
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(tmp_path / "login.json"))
    monkeypatch.setattr("lightning_sdk.api.llm_api.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("lightning_sdk.api.llm_api.Confirm.ask", lambda *_args, **_kwargs: True)
    previous = keyring.get_keyring()
    keyring.set_keyring(MemoryKeyring())
    platform = FakePlatform()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", platform.url)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", platform.url)
    browser = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", browser.open)
    try:
        litai_authenticate("story-model")
        assert len(platform.authorizations) == 1
        assert not platform.sign_ins
        assert cli_login.current_login() is not None
    finally:
        browser.finish()
        platform.stop()
        keyring.set_keyring(previous)


def test_litai_does_nothing_when_a_credential_already_exists(monkeypatch):
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "env-token")
    asked = []
    monkeypatch.setattr(
        "lightning_sdk.api.llm_api.Confirm.ask",
        lambda *_args, **_kwargs: asked.append(True) or True,
    )
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda *_args, **_kwargs: opened.append(True))

    litai_authenticate("story-model")

    assert asked == []
    assert opened == []
