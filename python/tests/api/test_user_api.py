from unittest import mock

import pytest

from lightning_sdk.api.user_api import UserApi
from lightning_sdk.lightning_cloud.openapi import (
    V1GetUserResponse,
    V1Secret,
    V1SecretType,
    V1UserFeatures,
)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_api(internal_user_api_mocker, monkeypatch):
    user_api = UserApi()

    user = user_api.get_user("user-abc")
    assert isinstance(user, V1GetUserResponse)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_api_valueerror(internal_user_api_mocker, monkeypatch):
    monkeypatch.setenv("LIGHTNING_USERNAME", "other-dummy")
    user_api = UserApi()

    with pytest.raises(ValueError, match="User xyz does not exist"):
        user_api.get_user("xyz")


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_get_user",
    autospec=True,
    return_value=V1GetUserResponse(features=V1UserFeatures(plugin_sweeps=True)),
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_api_get_feature_flags(mocker):
    user_api = UserApi()
    feature_flags = user_api._get_feature_flags()
    assert mocker.call_count == 1

    # These are some random feature flags that are currently available.
    # If this test fails because they were removed, it needs to be updated to new flags here and in the mock above
    assert feature_flags.plugin_sweeps


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_secrets():
    user_api = UserApi()

    mock_secrets = [
        V1Secret(id="secret-1", name="API_KEY", type=V1SecretType.UNSPECIFIED),
        V1Secret(id="secret-2", name="DATABASE_URL", type=V1SecretType.UNSPECIFIED),
    ]

    with mock.patch.object(user_api, "_get_secrets", return_value=mock_secrets):
        secrets = user_api.get_secrets()

    assert len(secrets) == 2
    assert secrets["API_KEY"] == "***REDACTED***"
    assert secrets["DATABASE_URL"] == "***REDACTED***"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_set_secret_create_new():
    user_api = UserApi()

    existing_secrets = [
        V1Secret(id="secret-1", name="API_KEY"),
    ]

    with mock.patch.object(user_api, "_get_secrets", return_value=existing_secrets), mock.patch.object(
        user_api, "_create_secret"
    ) as mock_create:
        user_api.set_secret("NEW_SECRET", "secret_value")

        mock_create.assert_called_once_with("NEW_SECRET", "secret_value")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_set_secret_update_existing():
    user_api = UserApi()

    existing_secrets = [
        V1Secret(id="secret-1", name="API_KEY"),
        V1Secret(id="secret-2", name="DATABASE_URL"),
    ]

    with mock.patch.object(user_api, "_get_secrets", return_value=existing_secrets), mock.patch.object(
        user_api, "_update_secret"
    ) as mock_update:
        user_api.set_secret("API_KEY", "new_secret_value")

        mock_update.assert_called_once_with("secret-1", "new_secret_value")


@mock.patch("lightning_sdk.api.user_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_secrets_api_call(mock_client):
    mock_client().secret_service_list_user_secrets.return_value.secrets = [
        V1Secret(id="secret-1", name="API_KEY"),
    ]

    user_api = UserApi()
    result = user_api._get_secrets()

    mock_client().secret_service_list_user_secrets.assert_called_once()
    assert len(result) == 1
    assert result[0].name == "API_KEY"


@mock.patch("lightning_sdk.api.user_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_create_secret_api_call(mock_client):
    user_api = UserApi()

    user_api._create_secret("NEW_SECRET", "secret_value")

    mock_client().secret_service_create_user_secret.assert_called_once()
    call_args = mock_client().secret_service_create_user_secret.call_args
    assert call_args[1]["body"].name == "NEW_SECRET"
    assert call_args[1]["body"].value == "secret_value"


@mock.patch("lightning_sdk.api.user_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_update_secret_api_call(mock_client):
    user_api = UserApi()

    user_api._update_secret("secret-1", "new_value")

    mock_client().secret_service_update_user_secret.assert_called_once()
    call_args = mock_client().secret_service_update_user_secret.call_args
    assert call_args[1]["id"] == "secret-1"
    assert call_args[1]["body"].value == "new_value"


@pytest.mark.parametrize(
    ("secret_name", "expected"),
    [
        ("VALID_SECRET", True),
        ("valid_secret", True),
        ("_VALID_SECRET", True),
        ("_valid_secret", True),
        ("SECRET_123", True),
        ("secret123", True),
        ("a", True),
        ("_", True),
        ("A_B_C_123", True),
        ("123_INVALID", False),  # starts with number
        ("INVALID-SECRET", False),  # contains hyphen
        ("INVALID SECRET", False),  # contains space
        ("INVALID.SECRET", False),  # contains dot
        ("", False),  # empty string
        ("INVALID@SECRET", False),  # contains special character
        ("INVALID#SECRET", False),  # contains hash
        ("INVALID$SECRET", False),  # contains dollar sign
    ],
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_verify_secret_name(secret_name, expected):
    user_api = UserApi()
    result = user_api.verify_secret_name(secret_name)
    assert result == expected


@mock.patch("lightning_sdk.api.user_api.LightningClient")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_create_teamspace(mock_client):
    user_api = UserApi()

    user_api.create_teamspace("my-teamspace")

    mock_client().projects_service_create_project.assert_called_once()
    call_args = mock_client().projects_service_create_project.call_args
    assert call_args[1]["body"].name == "my-teamspace"
    assert call_args[1]["body"].display_name == "my-teamspace"
