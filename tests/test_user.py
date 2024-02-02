from lightning_sdk.user import User
from lightning_sdk.teamspace import Teamspace

import pytest
from unittest import mock
import os


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
