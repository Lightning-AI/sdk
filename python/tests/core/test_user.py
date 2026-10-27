import os
from unittest import mock

import pytest

from lightning_sdk.user import User


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_init_from_name(internal_user_api_mocker):
    user = User("my-user-name")

    assert user.name == "my-user-name"
    assert user.id == "my-user-name"


@mock.patch.dict(os.environ, {"LIGHTNING_USERNAME": "my-user-name"})
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_init_from_env_var(internal_user_api_mocker):
    user = User()

    assert user.name == "my-user-name"
    assert user.id == "my-user-name"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_owns_no_teamspaces(internal_user_api_mocker):
    user = User("user-abc")

    with pytest.raises(ValueError, match="Users can't own teamspaces.*'<org>/<teamspace>'"):
        _ = user.teamspaces

    with pytest.raises(ValueError, match="Users can't own teamspaces.*'<org>/<teamspace>'"):
        user.create_teamspace("new-teamspace")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_equality(internal_user_api_mocker):
    assert User("my-username") == User("my-username")
    assert User("my-username") != User("your-username")


class SubUser(User):
    pass


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_inequality_user_subclass(internal_user_api_mocker):
    assert User("my-username") != SubUser("my-username")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_repr(internal_user_api_mocker):
    user = User("my-user-name")
    assert repr(user) == "User(name=my-user-name)"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_str(internal_user_api_mocker):
    user = User("my-user-name")
    assert str(user) == "User(name=my-user-name)"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_secrets_property(internal_user_api_mocker):
    user = User("my-user-name")

    mock_secrets = {"API_KEY": "***REDACTED***", "DATABASE_URL": "***REDACTED***"}

    with mock.patch.object(user._user_api, "get_secrets", return_value=mock_secrets) as mock_get:
        secrets = user.secrets

    assert secrets == mock_secrets
    mock_get.assert_called_once()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_set_secret(internal_user_api_mocker):
    user = User("my-user-name")

    with mock.patch.object(user._user_api, "set_secret") as mock_set:
        user.set_secret("NEW_SECRET", "secret_value")

    mock_set.assert_called_once_with("NEW_SECRET", "secret_value")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_set_secret_invalid_name(internal_user_api_mocker):
    user = User("my-user-name")

    with pytest.raises(
        ValueError,
        match="Secret keys must only contain alphanumeric characters and underscores and not begin with a number.",
    ):
        user.set_secret("123_INVALID", "secret_value")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_delete_secret(internal_user_api_mocker):
    user = User("my-user-name")

    with mock.patch.object(user._user_api, "delete_secret") as mock_delete:
        user.delete_secret("OLD_SECRET")

    mock_delete.assert_called_once_with("OLD_SECRET")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_user_delete_secret_invalid_name(internal_user_api_mocker):
    user = User("my-user-name")

    with mock.patch.object(user._user_api, "delete_secret") as mock_delete, pytest.raises(
        ValueError,
        match="Secret keys must only contain alphanumeric characters and underscores and not begin with a number.",
    ):
        user.delete_secret("123_INVALID")

    mock_delete.assert_not_called()
