import importlib.util
import time
import webbrowser

import keyring
import pytest

from lightning_sdk.lightning_cloud import env, login
from lightning_sdk.lightning_cloud.login import Auth, AuthServer
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, FakePlatform
from tests.lightning_cloud.utils.keyrings import MemoryKeyring


@pytest.fixture(autouse=True)
def keep_alive_mocker():  # noqa: PT004
    """Replace the SDK fixture that mocks threading.Thread for every test.

    The fake platform and browser each serve from a real thread.
    """


def _load_vendored_login():
    spec = importlib.util.spec_from_file_location("_vendored_login", login.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VENDORED = _load_vendored_login()


@pytest.fixture(autouse=True)
def _vendored_login(monkeypatch):
    """Put back the vendored interim login, which the SDK CLI replaces when imported.

    Collecting any test that imports lightning_sdk.cli applies that replacement,
    which keeps no reference to the vendored methods, so they come from a fresh load.
    """
    monkeypatch.setattr(Auth, "save", _VENDORED.Auth.save)
    monkeypatch.setattr(AuthServer, "login_with_browser", _VENDORED.AuthServer.login_with_browser)


@pytest.fixture(autouse=True)
def isolated_login(_clear_lightning_env_vars, tmp_path, monkeypatch):
    """Keep every test away from the real ~/.lightning, keychain and browser.

    The SDK's conftest sets a dummy LIGHTNING_API_KEY and LIGHTNING_AUTH_TOKEN,
    which these tests must choose for themselves.
    """
    for name in (
        "LIGHTNING_AUTH_TOKEN_FILE",
        "LIGHTNING_AUTH_TOKEN",
        "LIGHTNING_API_KEY",
        "LIGHTNING_USER_ID",
        "LIGHTNING_CLI_OIDC_LOGIN",
        "LIGHTNING_DEPLOYMENT_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    credentials = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", credentials)
    monkeypatch.setenv("LIGHTNING_CREDENTIAL_PATH", str(credentials))
    login_path = tmp_path / "login.json"
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(login_path))
    monkeypatch.setenv("LIGHTNING_LOGIN_PATH", str(login_path))

    def refuse_browser(url, *args, **kwargs):
        raise AssertionError("a test opened the real browser")

    monkeypatch.setattr(webbrowser, "open", refuse_browser)

    previous = keyring.get_keyring()
    memory = MemoryKeyring()
    keyring.set_keyring(memory)
    try:
        yield memory
    finally:
        keyring.set_keyring(previous)


@pytest.fixture()
def _oidc_login(monkeypatch):
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")


@pytest.fixture()
def platform(monkeypatch):
    fake = FakePlatform()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", fake.url)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", fake.url)
    yield fake
    fake.stop()


@pytest.fixture()
def browser(platform, monkeypatch):
    fake = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", fake.open)
    yield fake
    fake.finish()


class Clock:
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture()
def clock(monkeypatch):
    """One clock for the SDK and the fake platform, moved only by the test."""
    fake = Clock()
    monkeypatch.setattr(time, "time", fake)
    return fake
