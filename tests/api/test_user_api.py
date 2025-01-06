from unittest import mock

import pytest

from lightning_sdk.api.user_api import UserApi
from lightning_sdk.lightning_cloud.openapi import V1GetUserResponse, V1UserFeatures


def test_user_api(internal_user_api_mocker, monkeypatch):
    user_api = UserApi()

    user = user_api.get_user("user-abc")
    assert isinstance(user, V1GetUserResponse)


def test_user_api_valueerror(internal_user_api_mocker, monkeypatch):
    monkeypatch.setenv("LIGHTNING_USERNAME", "other-dummy")
    user_api = UserApi()

    with pytest.raises(ValueError, match="User xyz does not exist"):
        user_api.get_user("xyz")


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_get_user",
    autospec=True,
    return_value=V1GetUserResponse(features=V1UserFeatures(plugin_sweeps=True, jobs_v2=True)),
)
def test_user_api_get_feature_flags(mocker):
    user_api = UserApi()
    feature_flags = user_api._get_feature_flags()
    assert mocker.call_count == 1

    # These are some random feature flags that are currently available.
    # If this test fails because they were removed, it needs to be updated to new flags here and in the mock above
    assert feature_flags.plugin_sweeps
    assert feature_flags.jobs_v2
    assert not feature_flags.enable_efs
