"""LitAI, LitServe and license validation stay on the credential source."""

import threading
import webbrowser

import click
import pytest

from lightning_sdk.api.license_api import LicenseApi
from lightning_sdk.api.llm_api import authenticate as litai_authenticate
from lightning_sdk.cli.legacy.deploy._auth import _AuthMode
from lightning_sdk.cli.legacy.deploy._auth import authenticate as litserve_authenticate
from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, FakePlatform

_REAL_THREAD = threading.Thread


def _clear_credentials(monkeypatch, tmp_path):
    threading.Thread = _REAL_THREAD
    for name in ("LIGHTNING_AUTH_TOKEN", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("LIGHTNING_CLI_OIDC_LOGIN", raising=False)
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


def test_litai_puts_okbhrt_and_litaimodel_on_the_interim_sign_in(monkeypatch, tmp_path):
    _clear_credentials(monkeypatch, tmp_path)
    monkeypatch.setattr("lightning_sdk.api.llm_api.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("lightning_sdk.api.llm_api.Confirm.ask", lambda *_args, **_kwargs: True)
    platform = FakePlatform()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", platform.url)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", platform.url)
    browser = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", browser.open)
    try:
        litai_authenticate("story-model")
        query = platform.sign_ins[0]
        assert query["okbhrt"] == "x334uv8t7v"
        assert query["litaimodel"] == "story-model"
        assert not platform.authorizations
    finally:
        browser.finish()
        platform.stop()


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


def test_license_validation_leaves_the_saved_login_unchanged(monkeypatch, tmp_path):
    threading.Thread = _REAL_THREAD
    secrets = tmp_path / "credentials.json"
    original = b'{"auth_token": "sess_kept"}\n'
    secrets.write_bytes(original)
    monkeypatch.setattr(Auth, "secrets_file", secrets)
    platform = FakePlatform()
    platform.token_keys["license-token"] = "user-1"
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", platform.url)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", platform.url)
    try:
        LicenseApi("license-token")
        assert secrets.read_bytes() == original
    finally:
        platform.stop()
