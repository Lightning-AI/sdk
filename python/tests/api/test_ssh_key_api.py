import json
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.api.ssh_key_api import SSHKeyApi, SSHKeyRegistrationError

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample lightning@laptop"


def _response(status: int, body: dict) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.reason = "OK" if status < 400 else "Bad Request"
    response.data = json.dumps(body).encode()
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture()
def _login_token(monkeypatch):
    """Credentials as `lightning login` leaves them: a CLI session token and no API key."""
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN", "sess_cli-login-token")


def test_create_sends_the_public_key_with_the_login_token(_login_token) -> None:
    with patch("urllib3.PoolManager.request", return_value=_response(200, {"id": "key-1"})) as request:
        created = SSHKeyApi().create_public_key(name="lightning@laptop", public_key=PUBLIC_KEY)

    assert created.id == "key-1"
    request.assert_called_once()
    method, url = request.call_args.args[:2]
    assert method == "POST"
    assert url.endswith("/v1/ssh-keys")
    assert "?" not in url
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer sess_cli-login-token"
    assert json.loads(request.call_args.kwargs["body"]) == {"name": "lightning@laptop", "publicKey": PUBLIC_KEY}


def test_list_uses_the_login_token(_login_token) -> None:
    body = {"sshKeys": [{"id": "key-1", "name": "laptop", "publicKey": PUBLIC_KEY}]}
    with patch("urllib3.PoolManager.request", return_value=_response(200, body)) as request:
        keys = SSHKeyApi().list_public_keys()

    assert [key.public_key for key in keys] == [PUBLIC_KEY]
    method, url = request.call_args.args[:2]
    assert method == "GET"
    assert url.endswith("/v1/ssh-keys")
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer sess_cli-login-token"


def test_list_without_keys_is_empty(_login_token) -> None:
    with patch("urllib3.PoolManager.request", return_value=_response(200, {})):
        assert SSHKeyApi().list_public_keys() == []


def test_create_refusal_carries_the_platform_message(_login_token) -> None:
    refusal = "This SSH public key can't be added. Please generate a new key and add that instead."
    with patch(
        "urllib3.PoolManager.request", return_value=_response(400, {"code": 3, "message": refusal})
    ) as request, pytest.raises(SSHKeyRegistrationError) as error:
        SSHKeyApi().create_public_key(name="laptop", public_key=PUBLIC_KEY)

    assert str(error.value) == refusal
    request.assert_called_once()


def test_create_is_not_retried_on_a_server_error(_login_token) -> None:
    with patch(
        "urllib3.PoolManager.request", return_value=_response(500, {"code": 13, "message": "boom"})
    ) as request, pytest.raises(SSHKeyRegistrationError, match="boom"):
        SSHKeyApi().create_public_key(name="laptop", public_key=PUBLIC_KEY)

    request.assert_called_once()


def test_create_refusal_without_a_json_body_names_the_status(_login_token) -> None:
    response = _response(403, {})
    response.data = b"<html>blocked</html>"
    with patch("urllib3.PoolManager.request", return_value=response), pytest.raises(
        SSHKeyRegistrationError, match="HTTP 403"
    ):
        SSHKeyApi().create_public_key(name="laptop", public_key=PUBLIC_KEY)
