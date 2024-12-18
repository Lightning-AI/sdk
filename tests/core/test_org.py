import os
from unittest import mock

from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace


def test_org_init_from_name(internal_get_org_api_mocker):
    org = Organization("my-org-name")

    assert org.name == "my-org-name"
    assert org.id == "my-org-name"


@mock.patch.dict(os.environ, {"LIGHTNING_ORG": "my-org-name"})
def test_org_init_from_env_var(internal_get_org_api_mocker):
    org = Organization()

    assert org.name == "my-org-name"
    assert org.id == "my-org-name"


def test_org_teamspaces(internal_get_org_api_mocker, internal_teamspace_api_list_mocker):
    org = Organization("org-abc")

    teamspaces = org.teamspaces

    assert len(org.teamspaces) == 2
    for ts in teamspaces:
        assert isinstance(ts, Teamspace)
        assert ts.owner == org


def test_equality(internal_get_org_api_mocker):
    assert Organization("my-orgname") == Organization("my-orgname")
    assert Organization("my-orgname") != Organization("your-orgname")


class SubOrg(Organization):
    pass


def test_inequality_org_subclass(internal_get_org_api_mocker):
    assert Organization("my-orgname") != SubOrg("my-orgname")


def test_repr(internal_get_org_api_mocker):
    org = Organization("my-org-name")
    assert repr(org) == "Organization(name=my-org-name)"


def test_str(internal_get_org_api_mocker):
    org = Organization("my-org-name")
    assert str(org) == "Organization(name=my-org-name)"
