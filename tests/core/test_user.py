import os
from unittest import mock

import pytest

from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User


def test_user_init_from_name(internal_user_api_mocker):
    user = User("my-user-name")

    assert user.name == "my-user-name"
    assert user.id == "my-user-name"


@mock.patch.dict(os.environ, {"LIGHTNING_USERNAME": "my-user-name"})
def test_user_init_from_env_var(internal_user_api_mocker):
    user = User()

    assert user.name == "my-user-name"
    assert user.id == "my-user-name"


def test_user_teamspaces(internal_user_api_mocker, internal_teamspace_api_list_mocker):
    user = User("user-abc")

    teamspaces = user.teamspaces

    assert len(user.teamspaces) == 2
    for ts in teamspaces:
        assert isinstance(ts, Teamspace)
        assert ts.owner == user


def test_equality(internal_user_api_mocker):
    assert User("my-username") == User("my-username")
    assert User("my-username") != User("your-username")


class SubUser(User):
    pass


def test_inequality_user_subclass(internal_user_api_mocker):
    assert User("my-username") != SubUser("my-username")


def test_repr(internal_user_api_mocker):
    user = User("my-user-name")
    assert repr(user) == "User(name=my-user-name)"


def test_str(internal_user_api_mocker):
    user = User("my-user-name")
    assert str(user) == "User(name=my-user-name)"


def test_user_secrets_property(internal_user_api_mocker):
    user = User("my-user-name")

    mock_secrets = {"API_KEY": "***REDACTED***", "DATABASE_URL": "***REDACTED***"}

    with mock.patch.object(user._user_api, "get_secrets", return_value=mock_secrets) as mock_get:
        secrets = user.secrets

    assert secrets == mock_secrets
    mock_get.assert_called_once()


def test_user_set_secret(internal_user_api_mocker):
    user = User("my-user-name")

    with mock.patch.object(user._user_api, "set_secret") as mock_set:
        user.set_secret("NEW_SECRET", "secret_value")

    mock_set.assert_called_once_with("NEW_SECRET", "secret_value")


def test_user_set_secret_invalid_name(internal_user_api_mocker):
    user = User("my-user-name")

    with pytest.raises(
        ValueError,
        match="Secret keys must only contain alphanumeric characters and underscores and not begin with a number.",
    ):
        user.set_secret("123_INVALID", "secret_value")


@mock.patch("lightning_sdk.teamspace.Teamspace.__init__", return_value=None)
@mock.patch("lightning_sdk.user._get_authed_user")
def test_user_create_teamspace(mock_get_authed_user, mock_teamspace_init, internal_user_api_mocker):
    user = User("user-abc")
    mock_get_authed_user.return_value.id = user.id

    with mock.patch.object(user._user_api, "create_teamspace") as mock_create:
        user.create_teamspace("new-teamspace")

    mock_create.assert_called_once_with("new-teamspace")
    mock_teamspace_init.assert_called_once_with(name="new-teamspace", user=user)


@mock.patch("lightning_sdk.user._get_authed_user")
def test_user_create_teamspace_not_authed_user(mock_get_authed_user, internal_user_api_mocker):
    user = User("user-abc")
    mock_get_authed_user.return_value.id = "different-user-id"

    with pytest.raises(ValueError, match="Can only create teamspaces for currently authenticated user"):
        user.create_teamspace("new-teamspace")
