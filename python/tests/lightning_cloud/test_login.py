from typing import get_args

import pytest

from lightning_sdk.lightning_cloud.login import Auth, AuthOverride


def test_auth_no_longer_exposes_guest_login():
    assert not hasattr(Auth, "guest_login")


def test_auth_override_no_longer_accepts_guest():
    assert "guest" not in get_args(AuthOverride)


def test_missing_credentials_error_does_not_recommend_guest_login(monkeypatch, tmp_path):
    for name in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY", "LIGHTNING_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LIGHTNING_AUTH_TOKEN_FILE", str(tmp_path / "missing-token"))
    monkeypatch.setattr(Auth, "secrets_file", tmp_path / "credentials.json")
    monkeypatch.setattr(
        Auth,
        "_run_server",
        lambda self: (_ for _ in ()).throw(AssertionError("browser login is not expected")),
    )

    with pytest.raises(ValueError, match="No Lightning credentials are available") as exc_info:
        Auth().get_auth_header()

    assert "guest_login" not in str(exc_info.value)
