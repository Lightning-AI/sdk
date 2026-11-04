import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.login import Auth


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


@pytest.fixture()
def platform(monkeypatch, tmp_path):
    login_path = tmp_path / "login.json"
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(login_path))
    monkeypatch.setattr(env, "LIGHTNING_CLOUD_URL", "http://control-plane.test")
    monkeypatch.setattr(Auth, "secrets_file", tmp_path / "credentials.json")
    monkeypatch.setattr(cli_login.getpass, "getpass", lambda prompt: "the-code")
    calls = []

    def post(url, data=None, headers=None, timeout=None):
        calls.append((url, dict(data or {})))
        if url.endswith("/oidc/revoke"):
            return _Response(200, {})
        return _Response(
            200,
            {
                "access_token": "lit_ua_access",
                "refresh_token": "lit_ur_refresh",
                "expires_in": 3600,
                "refresh_expires_at": (datetime.now(timezone.utc) + timedelta(days=90))
                .isoformat()
                .replace("+00:00", "Z"),
                "lightning_grant": {"orgs": "all", "permissions": ["read", "write"]},
            },
        )

    monkeypatch.setattr(cli_login.requests, "post", post)
    return login_path, calls


def test_login_stores_the_pair_and_current_login_reads_it(platform, capsys):
    login_path, calls = platform

    login = cli_login.login(
        no_browser=True,
        insecure_storage=True,
        orgs=["acme", "beta"],
        project="team",
    )

    assert login.access_token == "lit_ua_access"
    assert login.refresh_token == "lit_ur_refresh"
    assert login.grant == {"orgs": "all", "permissions": ["read", "write"]}
    current = cli_login.current_login()
    assert current.storage == "file"
    assert current.grant == {"orgs": "all", "permissions": ["read", "write"]}

    saved = json.loads(login_path.read_text())
    assert saved["storage"] == "file"
    assert saved["access_token"] == "lit_ua_access"
    assert (login_path.stat().st_mode & 0o777) == 0o600

    url = next(word for word in capsys.readouterr().err.split() if "/oidc/authorize" in word)
    query = {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}
    assert query["orgs_hint"] == "acme,beta"
    assert query["project_hint"] == "team"
    assert query["redirect_uri"] == "http://control-plane.test/cli-login"

    form = calls[0][1]
    assert calls[0][0] == "http://control-plane.test/oidc/token"
    assert form["client_id"] == "lightning-cli"
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "the-code"
    assert form["code_verifier"]
    assert form["redirect_uri"] == "http://control-plane.test/cli-login"


def test_token_returns_the_access_token_and_logout_revokes_it(platform):
    login_path, calls = platform
    cli_login.login(no_browser=True, insecure_storage=True)

    assert cli_login.token() == "lit_ua_access"
    assert len(calls) == 1

    cli_login.logout()

    assert calls[-1][0] == "http://control-plane.test/oidc/revoke"
    assert calls[-1][1] == {"client_id": "lightning-cli", "token": "lit_ur_refresh"}
    assert not login_path.exists()


def test_login_refuses_without_a_keychain(monkeypatch, tmp_path):
    monkeypatch.setattr(env, "LIGHTNING_LOGIN_PATH", str(tmp_path / "login.json"))
    monkeypatch.setattr(cli_login, "_keychain_available", lambda: False)

    with pytest.raises(cli_login.LoginError, match="insecure-storage"):
        cli_login.login()


def test_file_login_is_readable_only_by_the_user(platform):
    login_path, _ = platform
    cli_login.login(no_browser=True, insecure_storage=True)

    assert os.stat(login_path).st_mode & 0o777 == 0o600
