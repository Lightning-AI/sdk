from unittest import mock
import pytest

from lightning_sdk.utils import (
    _resolve_org_name,
    _resolve_org,
    _resolve_user_name,
    _resolve_user,
    _resolve_teamspace_name,
    _resolve_teamspace,
)
from lightning_sdk.organization import Organization
from lightning_sdk.user import User
from lightning_sdk.teamspace import Teamspace
import os


@pytest.mark.parametrize("provided", [None, "abc"])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_org_name_no_env_var(provided):
    result = _resolve_org_name(provided)

    if provided is None:
        assert result is None
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_ORG": "abc",
    },
)
def test_resolve_org_name_env_var(provided):
    result = _resolve_org_name(provided)

    if provided is None:
        assert result == "abc"
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_ORG": "",
    },
)
def test_resolve_org_name_empty_env_var(provided):
    result = _resolve_org_name(provided)

    if provided is None:
        assert result is None
    else:
        assert result == provided


# TODO: update with org-name check once added
@pytest.mark.parametrize("provided", [None, "org_name", Organization(name="org_name")])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_org(provided):
    result = _resolve_org(provided)

    if provided is None:
        assert result is None
    elif isinstance(provided, Organization):
        assert result == provided
    else:
        assert isinstance(result, Organization)


@pytest.mark.parametrize("provided", [None, "abc"])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_user_name_no_env_var(provided):
    result = _resolve_user_name(provided)

    if provided is None:
        assert result is None
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_USERNAME": "abc",
    },
)
def test_resolve_user_name_env_var(provided):
    result = _resolve_user_name(provided)

    if provided is None:
        assert result == "abc"
    else:
        assert result == provided


# TODO: update with user-name check once added
@pytest.mark.parametrize("provided", [None, "user_name", User(name="user_name")])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_user(provided):
    result = _resolve_user(provided)

    if provided is None:
        assert result is None
    elif isinstance(provided, User):
        assert result == provided
    else:
        assert isinstance(result, User)


@pytest.mark.parametrize("provided", [None, "abc"])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_teamspace_name_no_env_var(provided):
    result = _resolve_teamspace_name(provided)

    if provided is None:
        assert result is None
    else:
        assert result == provided


@pytest.mark.parametrize("provided", [None, "abc", "def"])
@mock.patch.dict(
    os.environ,
    {
        "LIGHTNING_TEAMSPACE": "abc",
    },
)
def test_resolve_teamspace_name_env_var(provided):
    result = _resolve_teamspace_name(provided)

    if provided is None:
        assert result == "abc"
    else:
        assert result == provided


# TODO: Add name check once implemented
@pytest.mark.parametrize(
    "teamspace_name, org_name, user_name, expected_result",
    [
        ("team1", "org1", "user1", Teamspace(name="team1", org=Organization(name="org1"))),
        ("team2", None, "user2", Teamspace(name="team2", user=User(name="user2"))),
        ("team3", "org3", None, Teamspace(name="team3", org=Organization(name="org3"))),
    ],
)
def test_resolve_teamspace_combinations(teamspace_name, org_name, user_name, expected_result):
    with mock.patch.dict(os.environ, {"LIGHTNING_TEAMSPACE": teamspace_name}):
        org_env_var_value = org_name if org_name is not None else ""
        user_env_var_value = user_name if user_name is not None else ""

        with mock.patch.dict(
            os.environ, {"LIGHTNING_ORG": org_env_var_value, "LIGHTNING_USERNAME": user_env_var_value}
        ):
            org_result = _resolve_org_name(None) if org_name is None else Organization(name=org_name)
            user_result = _resolve_user_name(None) if user_name is None else User(name=user_name)

            result = _resolve_teamspace(None, org_result, user_result)
            assert isinstance(result, Teamspace)
