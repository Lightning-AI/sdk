"""Raw requests take a credential handler, and a 401 is retried once with a fresh token."""

import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import keyring
import pytest
import requests

from lightning_sdk.api.billing_api import BillingApi
from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.api.utils import CredentialAuth, _BlobUploader
from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.credentials import CredentialSource, start_login
from lightning_sdk.lightning_cloud.login import Auth
from tests.lightning_cloud.utils.fake_platform import FakeBrowser, FakePlatform
from tests.lightning_cloud.utils.keyrings import MemoryKeyring

_REAL_THREAD = threading.Thread
_LOGIN_FAILED = "Authentication failed. Please run `lightning login`."


class _RetryServer:
    """Answers 401 for ``old-token`` after rewriting the token file, then 200.

    With ``rotate=False`` the token file is left alone, so the 401 can't be refreshed.
    """

    def __init__(self, token_path, rotate=True):
        seen = []
        user_agents = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):  # noqa: N802
                self._reply()

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                if length:
                    self.rfile.read(length)
                self._reply()

            def _reply(self):
                token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                seen.append(token)
                user_agents.append(self.headers.get("User-Agent"))
                if token == "old-token":
                    if rotate:
                        token_path.write_text("new-token")
                    status, body = 401, b'{"error":"expired"}'
                elif "usage-report" in self.path:
                    status, body = 200, b"col\n"
                elif self.path.endswith("/blobs"):
                    status, body = 200, b'{"results":[]}'
                else:
                    status, body = 200, b'{"tree":[]}'
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                return

        self.seen = seen
        self.user_agents = user_agents
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._thread = _REAL_THREAD(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._httpd.shutdown()
        self._thread.join(timeout=5)
        self._httpd.server_close()


def _serve_token_file(monkeypatch, tmp_path, rotate):
    threading.Thread = _REAL_THREAD
    for name in ("LIGHTNING_AUTH_TOKEN", "LIGHTNING_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    token_path = tmp_path / "token"
    token_path.write_text("old-token")
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN_FILE", str(token_path))
    server = _RetryServer(token_path, rotate=rotate)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", server.url)
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", server.url)
    return server


@pytest.fixture()
def refreshed_token(monkeypatch, tmp_path):
    server = _serve_token_file(monkeypatch, tmp_path, rotate=True)
    yield server
    server.stop()


@pytest.fixture()
def stale_token(monkeypatch, tmp_path):
    server = _serve_token_file(monkeypatch, tmp_path, rotate=False)
    yield server
    server.stop()


def _blob_request(url, tmp_path):
    local = tmp_path / "blob.bin"
    local.write_bytes(b"hi")
    uploader = _BlobUploader(
        client=None,
        endpoint_base=f"{url}/v1/projects/ts/artifacts",
        file_path=str(local),
        remote_path="blob.bin",
        progress_bar=False,
    )
    uploader._post_blob_request("/blobs", {"path": "blob.bin"}, "request upload URLs for")


_RAW_PATHS = {
    "filesystem list": lambda url, tmp_path: FilesystemApi().list_files("ts", "data"),
    "filesystem download": lambda url, tmp_path: FilesystemApi()._download_single_file("a.bin", tmp_path / "a", "ts"),
    "studio tree": lambda url, tmp_path: StudioApi().get_tree("st", "ts", "data"),
    "teamspace tree": lambda url, tmp_path: TeamspaceApi().get_tree("ts", "data"),
    "billing csv": lambda url, tmp_path: BillingApi()._download_activity_csv(
        "/v1/billing/usage-report/download/detailed", "org"
    ),
    "blob upload": _blob_request,
}


@pytest.mark.parametrize("call", _RAW_PATHS.values(), ids=_RAW_PATHS.keys())
def test_a_raw_request_refused_with_a_401_no_refresh_fixes_says_to_log_in(stale_token, tmp_path, call):
    with pytest.raises(ConnectionError, match=re.escape(_LOGIN_FAILED)):
        call(stale_token.url, tmp_path)
    assert stale_token.seen == ["old-token"]


def test_a_raw_request_sends_the_sdk_user_agent(refreshed_token):
    FilesystemApi().list_files("ts", "data")
    assert refreshed_token.user_agents == [env.USER_AGENT, env.USER_AGENT]

    requests.get(
        f"{refreshed_token.url}/custom",
        headers={"User-Agent": "caller-agent"},
        auth=CredentialAuth(),
        timeout=5,
    )
    assert refreshed_token.user_agents[-1] == "caller-agent"

    prepared = requests.Request("GET", f"{refreshed_token.url}/bare").prepare()
    assert "User-Agent" not in prepared.headers
    CredentialAuth()(prepared)
    assert prepared.headers["User-Agent"] == env.USER_AGENT


def test_filesystem_list_retries_a_401(refreshed_token):
    FilesystemApi().list_files("ts", "data")
    assert refreshed_token.seen == ["old-token", "new-token"]


def test_studio_tree_retries_a_401(refreshed_token):
    StudioApi().get_tree("st", "ts", "data")
    assert refreshed_token.seen == ["old-token", "new-token"]


def test_teamspace_tree_retries_a_401(refreshed_token):
    TeamspaceApi().get_tree("ts", "data")
    assert refreshed_token.seen == ["old-token", "new-token"]


def test_billing_csv_retries_a_401(refreshed_token):
    BillingApi()._download_activity_csv("/v1/billing/usage-report/download/detailed", "org")
    assert refreshed_token.seen == ["old-token", "new-token"]


def test_blob_upload_retries_a_401(refreshed_token, tmp_path):
    _blob_request(refreshed_token.url, tmp_path)
    assert refreshed_token.seen == ["old-token", "new-token"]


def test_folder_download_refreshes_when_the_access_token_expires_midway(monkeypatch, tmp_path, inline_executor_cls):
    threading.Thread = _REAL_THREAD
    for name in ("LIGHTNING_AUTH_TOKEN", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LIGHTNING_CLI_OIDC_LOGIN", "1")
    monkeypatch.setattr(Auth, "secrets_file", tmp_path / "credentials.json")
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(tmp_path / "login.json"))
    previous = keyring.get_keyring()
    keyring.set_keyring(MemoryKeyring())
    platform = FakePlatform()
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", platform.url)
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", platform.url)
    browser = FakeBrowser(platform)
    monkeypatch.setattr(webbrowser, "open", browser.open)
    seen = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):  # noqa: N802
            token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            seen.append(token)
            if len(seen) == 1:
                platform.expire_access_tokens()
                status, body = 401, b"expired"
            elif platform.accepts(token):
                status, body = 200, b"x"
            else:
                status, body = 401, b"rejected"
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    download = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    download_thread = _REAL_THREAD(target=download.serve_forever, daemon=True)
    download_thread.start()
    try:
        start_login()
        browser.finish()
        first = CredentialSource().resolve().token
        api = StudioApi()
        api.list_files = lambda *_args, **_kwargs: [{"path": "a.bin", "size": 1}]
        api._client.api_client.configuration.host = f"http://127.0.0.1:{download.server_address[1]}"
        monkeypatch.setattr("lightning_sdk.api.studio_api.ThreadPoolExecutor", inline_executor_cls)
        api.download_folder("folder", str(tmp_path / "out"), "st", "ts", "cluster", progress_bar=False)
        assert seen[0] == first
        assert seen[1] != first
        assert platform.accepts(seen[1])
        assert (tmp_path / "out" / "a.bin").read_bytes() == b"x"
    finally:
        browser.finish()
        platform.stop()
        download.shutdown()
        download_thread.join(timeout=5)
        download.server_close()
        keyring.set_keyring(previous)
