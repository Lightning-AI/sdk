import json

import pytest

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.credentials import CredentialSource
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.rest_client import GridRestClient, create_swagger_client


class _Api:
    def __init__(self, request):
        self.request = request


@pytest.fixture()
def isolated_credentials(monkeypatch, tmp_path):
    for name in (
        "LIGHTNING_AUTH_TOKEN_FILE",
        "LIGHTNING_AUTH_TOKEN",
        "LIGHTNING_API_KEY",
        "LIGHTNING_USER_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    credentials = tmp_path / "credentials.json"
    monkeypatch.setattr(Auth, "secrets_file", credentials)
    monkeypatch.setattr(
        Auth,
        "_run_server",
        lambda self: (_ for _ in ()).throw(AssertionError("browser login is not expected")),
    )
    return credentials


def test_token_file_is_reread_between_requests(isolated_credentials, monkeypatch, tmp_path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("sess_one\n")
    monkeypatch.setenv(env.LIGHTNING_AUTH_TOKEN_FILE, str(token_file))
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])

    client = GridRestClient(api_client=_Api(request), with_auth=True)
    client.api_client.request("GET", "http://example")
    token_file.write_text("sess_two")
    client.api_client.request("GET", "http://example")

    assert seen == ["Bearer sess_one", "Bearer sess_two"]


def test_saved_api_key_is_bearer_and_never_basic(isolated_credentials, monkeypatch) -> None:
    isolated_credentials.write_text(json.dumps({"user_id": "user-1", "api_key": "key-1"}))
    monkeypatch.setenv("LIGHTNING_USER_ID", "user-1")
    monkeypatch.setenv("LIGHTNING_API_KEY", "key-1")

    assert CredentialSource().header() == "Bearer key-1"
    assert Auth().authenticate() == "Bearer key-1"
    assert Auth().auth_header == "Bearer key-1"
    assert Auth().get_auth_header("api_key") == "Bearer key-1"


def test_a_legacy_session_login_still_sends_bearer(isolated_credentials) -> None:
    isolated_credentials.write_text(json.dumps({"user_id": "user-1", "auth_token": "sess_interim"}))
    seen = []

    def request(method, url, headers=None, **kwargs):
        seen.append(headers["Authorization"])

    GridRestClient(api_client=_Api(request), with_auth=True).api_client.request("GET", "http://example")

    assert seen == ["Bearer sess_interim"]


def test_the_user_agent_names_the_installed_sdk() -> None:
    assert env.USER_AGENT.startswith("lightning-sdk/")
    assert create_swagger_client().user_agent == env.USER_AGENT
