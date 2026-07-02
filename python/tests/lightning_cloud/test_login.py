from typing import get_args

import pytest

from lightning_sdk.lightning_cloud.login import Auth, AuthOverride


def test_auth_no_longer_exposes_guest_login():
    assert not hasattr(Auth, "guest_login")


def test_auth_override_no_longer_accepts_guest():
    assert "guest" not in get_args(AuthOverride)


def test_missing_credentials_error_does_not_recommend_guest_login(monkeypatch):
    monkeypatch.delenv("LIGHTNING_USER_ID", raising=False)
    monkeypatch.delenv("LIGHTNING_API_KEY", raising=False)
    monkeypatch.delenv("LIGHTNING_AUTH_TOKEN", raising=False)

    with pytest.raises(ValueError, match="No authentication credentials available") as exc_info:
        Auth().get_auth_header()

    assert "guest_login" not in str(exc_info.value)
