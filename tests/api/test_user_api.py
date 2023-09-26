import pytest
from lightning_cloud.openapi import V1GetUserResponse

from lightning_sdk.api.user_api import UserApi


def test_user_api(internal_user_api_mocker, monkeypatch):
    monkeypatch.setenv("LIGHTNING_USERNAME", "user-abc")
    user_api = UserApi()

    org = user_api.get_user("user-abc")
    assert isinstance(org, V1GetUserResponse)


def test_user_api_valueerror(internal_user_api_mocker, monkeypatch):
    monkeypatch.setenv("LIGHTNING_USERNAME", "other-dummy")
    user_api = UserApi()

    with pytest.raises(ValueError, match="User xyz does not exist"):
        user_api.get_user("xyz")
