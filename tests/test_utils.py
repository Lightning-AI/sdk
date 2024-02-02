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


@pytest.mark.parametrize("provided", [None, "org_name", -1])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_org(internal_get_org_api_mocker, provided):
    # can't instantiate outside without proper mocking
    if provided == -1:
        provided = Organization(name="org_name")

    result = _resolve_org(provided)

    if provided is None:
        assert result is None
    elif isinstance(provided, Organization):
        assert result == provided
    else:
        assert isinstance(result, Organization)
        assert result.name == provided


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


@pytest.mark.parametrize("provided", [None, "user_name", -1])
@mock.patch.dict(os.environ, clear=True)
def test_resolve_user(internal_user_api_mocker, provided):
    # can't instantiate outside without proper mocking
    if provided == -1:
        provided = User(name="user_name")

    result = _resolve_user(provided)

    if provided is None:
        assert result is None
    elif isinstance(provided, User):
        assert result == provided
    else:
        assert isinstance(result, User)
        assert result.name == provided


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


@pytest.mark.parametrize(
    "teamspace_name, org_name, user_name, expected_result",
    [
        ("ts-abc", "org-abc", "user1", {"name": "ts-abc", "org": {"name": "org-abc"}}),
        ("ts-abc", None, "user-abc", {"name": "ts-abc", "user": {"name": "user-abc"}}),
        ("ts-def", "org-abc", None, {"name": "ts-def", "org": {"name": "org-abc"}}),
    ],
)
def test_resolve_teamspace_combinations(
    internal_user_api_mocker,
    internal_get_org_api_mocker,
    resolve_all_teamspaces_api_mocker,
    teamspace_name,
    org_name,
    user_name,
    expected_result,
):
    with mock.patch.dict(os.environ, {"LIGHTNING_TEAMSPACE": teamspace_name}):
        org_env_var_value = org_name if org_name is not None else ""
        user_env_var_value = user_name if user_name is not None else ""

        with mock.patch.dict(
            os.environ, {"LIGHTNING_ORG": org_env_var_value, "LIGHTNING_USERNAME": user_env_var_value}
        ):
            result = _resolve_teamspace(None, org_name, user_name)

            assert isinstance(result, Teamspace)

            expected_org = expected_result.get("org", {})
            expected_org_name = expected_org.get("name", None)
            expected_user = expected_result.get("user", {})
            expected_user_name = expected_user.get("name", None)

            assert result == Teamspace(
                teamspace_name, org=_resolve_org(expected_org_name), user=_resolve_user(expected_user_name)
            )
