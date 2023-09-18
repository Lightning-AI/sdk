import pytest
from lightning_cloud.openapi import V1SearchUser

from lightning_sdk.api.user_api import UserApi


def test_user_api(internal_user_api_mocker, monkeypatch):
    user_api = UserApi()

    user = user_api.get_user("user-abc")
    assert isinstance(user, V1SearchUser)


def test_user_api_valueerror(internal_user_api_mocker, monkeypatch):
    monkeypatch.setenv('LIGHTNING_USERNAME', 'other-dummy')
    user_api = UserApi()

    with pytest.raises(ValueError, match="User xyz does not exist"):
        user_api.get_user("xyz")
