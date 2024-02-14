from lightning_sdk.user import User
from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
import pytest
import os
from unittest import mock
from contextlib import nullcontext


@pytest.mark.parametrize("user", ["user-abc", None, -1])
@pytest.mark.parametrize("org", ["org-abc", None, -1])
@mock.patch.dict(os.environ, clear=True)
def test_teamspace_init(
    internal_teamspace_api_list_mocker, internal_user_api_mocker, internal_get_org_api_mocker, user, org
):
    # convert -1 to actual objects since we can't do that outside without mocking API calls
    if user == -1:
        user = User("user-abc")

    if org == -1:
        org = Organization("org-abc")

    if user is None and org is None:
        context = pytest.raises(
            RuntimeError,
            match="Neither user or org are specified, but one of them has to be the owner of the Teamspace",
        )
    elif user is not None and org is not None:
        context = pytest.raises(
            ValueError, match="User and org are mutually exclusive. Please only specify the one who owns the teamspace."
        )
    else:
        context = nullcontext()

    with context:
        Teamspace("ts-abc", user=user, org=org)


@pytest.mark.parametrize("user", ["user-abc", None, -1])
@pytest.mark.parametrize("org", ["org-abc", None, -1])
def test_teamspace_init_env(
    internal_teamspace_api_list_mocker, internal_user_api_mocker, internal_get_org_api_mocker, user, org
):
    if user is None and org is None:
        context = pytest.raises(
            RuntimeError,
            match="Neither user or org are specified, but one of them has to be the owner of the Teamspace",
        )
    elif user is not None and org is not None:
        if user == -1 or org == -1:
            context = nullcontext()
        else:
            context = pytest.raises(
                ValueError,
                match="User and org are mutually exclusive. Please only specify the one who owns the teamspace.",
            )
    else:
        context = nullcontext()

    new_dict = {}
    if user == -1:
        new_dict["LIGHTNING_USERNAME"] = "user-abc"
        user = None

    if org == -1:
        new_dict["LIGHTNING_ORG"] = "org-abc"
        org = None

    with context, mock.patch.dict(os.environ, new_dict, clear=True):
        print(user, org)
        Teamspace("ts-abc", user=user, org=org)


@mock.patch.dict(os.environ, clear=True)
def test_teamspace_list_clusters_studios_user(
    internal_studio_api_list_mocker,
    internal_user_api_mocker,
    internal_teamspace_api_cluster_list_mocker,
    internal_teamspace_api_list_mocker,
    internal_auth_mocker,
):
    ts = Teamspace("ts-abc", user="user-abc")

    studios = ts.studios

    # 2 clusters * 3 studios per cluster
    assert len(studios) == 6


@mock.patch.dict(os.environ, clear=True)
def test_teamspace_list_clusters_studios_org(
    internal_studio_api_list_mocker,
    internal_get_org_api_mocker,
    internal_teamspace_api_cluster_list_mocker,
    internal_teamspace_api_list_mocker,
    internal_auth_mocker,
):
    ts = Teamspace("ts-abc", org="org-abc")

    studios = ts.studios

    # 2 clusters * 3 studios per cluster
    assert len(studios) == 6


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"user": "user-abc"}, "Teamspace(name=ts-abc, owner=User(name=user-abc))"),
        ({"org": "org-abc"}, "Teamspace(name=ts-abc, owner=Organization(name=org-abc))"),
    ],
)
def test_repr(
    internal_teamspace_api_list_mocker,
    internal_get_org_api_mocker,
    internal_user_api_mocker,
    internal_auth_mocker,
    kwargs,
    expected,
):
    ts = Teamspace(name="ts-abc", **kwargs)
    assert repr(ts) == expected


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"user": "user-abc"}, "Teamspace(name=ts-abc, owner=User(name=user-abc))"),
        ({"org": "org-abc"}, "Teamspace(name=ts-abc, owner=Organization(name=org-abc))"),
    ],
)
def test_str(
    internal_teamspace_api_list_mocker,
    internal_get_org_api_mocker,
    internal_user_api_mocker,
    internal_auth_mocker,
    kwargs,
    expected,
):
    ts = Teamspace(name="ts-abc", **kwargs)
    assert str(ts) == expected


def test_teamspace_error_user_and_org():
    with pytest.raises(
        ValueError, match="User and org are mutually exclusive. Please only specify the one who owns the teamspace."
    ):
        Teamspace(name="ts-abc", user="foo", org="bar")
