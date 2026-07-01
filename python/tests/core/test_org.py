import os
from unittest import mock

from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_init_from_name(internal_get_org_api_mocker):
    org = Organization("my-org-name")

    assert org.name == "my-org-name"
    assert org.id == "my-org-name"


@mock.patch.dict(os.environ, {"LIGHTNING_ORG": "my-org-name"})
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_init_from_env_var(internal_get_org_api_mocker):
    org = Organization()

    assert org.name == "my-org-name"
    assert org.id == "my-org-name"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_teamspaces(internal_get_org_api_mocker, internal_teamspace_api_list_mocker):
    org = Organization("org-abc")

    teamspaces = org.teamspaces

    assert len(org.teamspaces) == 2
    for ts in teamspaces:
        assert isinstance(ts, Teamspace)
        assert ts.owner == org


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_equality(internal_get_org_api_mocker):
    assert Organization("my-orgname") == Organization("my-orgname")
    assert Organization("my-orgname") != Organization("your-orgname")


class SubOrg(Organization):
    pass


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_inequality_org_subclass(internal_get_org_api_mocker):
    assert Organization("my-orgname") != SubOrg("my-orgname")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_repr(internal_get_org_api_mocker):
    org = Organization("my-org-name")
    assert repr(org) == "Organization(name=my-org-name)"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_str(internal_get_org_api_mocker):
    org = Organization("my-org-name")
    assert str(org) == "Organization(name=my-org-name)"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_default_cloud_account(internal_get_org_api_mocker):
    org = Organization("my-org-name")
    assert org.default_cloud_account == "my-preferred-cluster"

    # simulate empty response
    org._org.preferred_cluster = ""

    assert org.default_cloud_account is None


@mock.patch("lightning_sdk.teamspace.Teamspace.__init__", return_value=None)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_org_create_teamspace(mock_teamspace_init, internal_get_org_api_mocker):
    org = Organization("my-org-name")

    with mock.patch.object(org._org_api, "create_teamspace") as mock_create:
        org.create_teamspace("new-teamspace")

    mock_create.assert_called_once_with("new-teamspace", org.id)
    mock_teamspace_init.assert_called_once_with(name="new-teamspace", org=org)
