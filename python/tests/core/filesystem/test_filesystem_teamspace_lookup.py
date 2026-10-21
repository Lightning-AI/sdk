from types import SimpleNamespace
from unittest import mock

import pytest

from lightning_sdk.filesystem import Filesystem
from lightning_sdk.lightning_cloud.openapi.rest import ApiException

FAKE_AUTH_HEADERS = {"Authorization": "Bearer fake-token"}
HOST = "https://lightning.ai"
ORG_ID = "org-1"
TEAMSPACE_ID = "ts-123"


def membership(project_id, name, owner_id=ORG_ID, display_name=""):
    return SimpleNamespace(project_id=project_id, name=name, display_name=display_name, owner_id=owner_id)


@pytest.fixture()
def client():
    with mock.patch("lightning_sdk.api.utils.LightningClient") as client_cls:
        client = client_cls.return_value
        client.api_client.configuration.host = HOST
        client.organizations_service_get_organization.return_value = SimpleNamespace(id=ORG_ID)
        client.projects_service_list_memberships.return_value = SimpleNamespace(
            memberships=[
                membership("ts-other", "my-teamspace", owner_id="org-2"),
                membership(TEAMSPACE_ID, "my-teamspace"),
            ]
        )
        yield client


@pytest.fixture()
def tree():
    with (
        mock.patch(
            "lightning_sdk.api.filesystem_api._authenticate_and_get_auth_headers",
            return_value=FAKE_AUTH_HEADERS,
        ),
        mock.patch("lightning_sdk.api.filesystem_api.requests.get") as get,
    ):
        get.return_value.status_code = 200
        get.return_value.json.return_value = {"tree": [{"path": "data/a.txt", "type": "blob", "size": 1}]}
        yield get


@mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace")
def test_org_teamspace_resolves_from_org_and_memberships(resolve_teamspace, client, tree):
    assert Filesystem().listdir("lit://my-org/my-teamspace/data") == ["a.txt"]

    client.organizations_service_get_organization.assert_called_once_with(id="", name="my-org")
    client.projects_service_list_memberships.assert_called_once_with(filter_by_user_id=True)
    client.projects_service_get_project.assert_not_called()
    resolve_teamspace.assert_not_called()
    assert f"/v1/projects/{TEAMSPACE_ID}/artifacts/trees/data" in tree.call_args[0][0]


@mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace")
def test_teamspace_matches_display_name(resolve_teamspace, client, tree):
    client.projects_service_list_memberships.return_value = SimpleNamespace(
        memberships=[membership(TEAMSPACE_ID, "general", display_name="My Teamspace")]
    )

    Filesystem().listdir("lit://my-org/My Teamspace/data")

    resolve_teamspace.assert_not_called()
    assert f"/v1/projects/{TEAMSPACE_ID}/" in tree.call_args[0][0]


@mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace")
def test_user_owner_falls_back_to_full_resolution(resolve_teamspace, client, tree):
    client.organizations_service_get_organization.side_effect = ApiException(status=404, reason="Not Found")
    resolve_teamspace.return_value = SimpleNamespace(id="ts-user", name="my-teamspace")

    Filesystem().listdir("lit://my-user/my-teamspace/data")

    resolve_teamspace.assert_called_once_with("my-teamspace", "my-user")
    assert "/v1/projects/ts-user/" in tree.call_args[0][0]


@mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace")
def test_relative_url_falls_back_to_full_resolution(resolve_teamspace, client, tree):
    resolve_teamspace.return_value = SimpleNamespace(id="ts-current", name="current")

    Filesystem().listdir("lit:///data")

    client.organizations_service_get_organization.assert_not_called()
    resolve_teamspace.assert_called_once_with(None, None)


def test_org_lookup_error_other_than_not_found_is_raised(client, tree):
    client.organizations_service_get_organization.side_effect = ApiException(status=500, reason="Internal")

    with pytest.raises(ApiException):
        Filesystem().listdir("lit://my-org/my-teamspace/data")


def test_ambiguous_teamspace_name_is_an_error(client, tree):
    client.projects_service_list_memberships.return_value = SimpleNamespace(
        memberships=[membership("ts-1", "my-teamspace"), membership("ts-2", "x", display_name="my-teamspace")]
    )

    with pytest.raises(RuntimeError, match="no unique name"):
        Filesystem().listdir("lit://my-org/my-teamspace/data")


@mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace")
def test_download_uses_the_lean_lookup(resolve_teamspace, client, tree, tmp_path):
    def fake_get(url, **kwargs):
        resp = mock.MagicMock()
        resp.status_code = 200
        if "trees" in url:
            resp.json.return_value = {"tree": [{"path": "data/a.txt", "type": "blob", "size": 1}]}
        else:
            resp.headers = {"content-length": "1"}
            resp.iter_content.side_effect = lambda *a, **kw: iter([b"x"])
        return resp

    tree.side_effect = fake_get
    target = tmp_path / "a.txt"

    Filesystem().copy("lit://my-org/my-teamspace/data/a.txt", str(target))

    assert target.read_bytes() == b"x"
    client.projects_service_get_project.assert_not_called()
    resolve_teamspace.assert_not_called()
    urls = [c[0][0] for c in tree.call_args_list]
    assert any(f"/v1/projects/{TEAMSPACE_ID}/artifacts/blobs/data/a.txt" in url for url in urls)
