from types import SimpleNamespace
from unittest import mock

import pytest

from lightning_sdk.cli.ls import ls_impl
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


def test_org_teamspace_resolves_from_org_and_memberships(client, tree):
    assert Filesystem().listdir("lit://my-org/my-teamspace/data") == ["a.txt"]

    client.organizations_service_get_organization.assert_called_once_with(id="", name="my-org")
    client.projects_service_list_memberships.assert_called_once_with(filter_by_user_id=True)
    client.projects_service_get_project.assert_not_called()
    assert f"/v1/projects/{TEAMSPACE_ID}/artifacts/trees/data" in tree.call_args[0][0]


def test_teamspace_matches_display_name(client, tree):
    client.projects_service_list_memberships.return_value = SimpleNamespace(
        memberships=[membership(TEAMSPACE_ID, "general", display_name="My Teamspace")]
    )

    Filesystem().listdir("lit://my-org/My Teamspace/data")

    assert f"/v1/projects/{TEAMSPACE_ID}/" in tree.call_args[0][0]


def test_unknown_org_is_an_error(client, tree):
    client.organizations_service_get_organization.side_effect = ApiException(status=404, reason="Not Found")

    with pytest.raises(ValueError, match="Org nope does not exist"):
        Filesystem().listdir("lit://nope/my-teamspace/data")
    tree.assert_not_called()


def test_teamspace_not_in_memberships_is_an_error(client, tree):
    with pytest.raises(ValueError, match="Teamspace missing does not exist"):
        Filesystem().listdir("lit://my-org/missing/data")
    client.projects_service_get_project.assert_not_called()
    tree.assert_not_called()


@pytest.fixture()
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    with mock.patch("lightning_sdk.utils.config._DEFAULT_CONFIG_FILE_PATH", str(path)):
        yield path


def test_relative_url_uses_teamspace_from_env(client, tree, config_file, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TEAMSPACE", "my-teamspace")
    monkeypatch.setenv("LIGHTNING_ORG", "my-org")

    Filesystem().listdir("lit:///data")

    client.organizations_service_get_organization.assert_called_once_with(id="", name="my-org")
    client.projects_service_get_project.assert_not_called()
    assert f"/v1/projects/{TEAMSPACE_ID}/artifacts/trees/data" in tree.call_args[0][0]


def test_relative_url_uses_teamspace_from_config(client, tree, config_file):
    config_file.write_text("teamspace:\n  name: my-teamspace\n  owner: my-org\n  owner_type: organization\n")

    Filesystem().listdir("lit:///data")

    client.organizations_service_get_organization.assert_called_once_with(id="", name="my-org")
    assert f"/v1/projects/{TEAMSPACE_ID}/" in tree.call_args[0][0]


def test_relative_url_without_a_current_teamspace_is_an_error(client, tree, config_file):
    with pytest.raises(ValueError, match="Could not resolve a teamspace"):
        Filesystem().listdir("lit:///data")
    client.organizations_service_get_organization.assert_not_called()


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


def test_download_uses_the_lean_lookup(client, tree, tmp_path):
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
    urls = [c[0][0] for c in tree.call_args_list]
    assert any(f"/v1/projects/{TEAMSPACE_ID}/artifacts/blobs/data/a.txt" in url for url in urls)


def test_ls_uses_the_lean_lookup(client, tree, capsys):
    def fake_get(url, **kwargs):
        resp = mock.MagicMock()
        resp.status_code = 200
        if url.endswith("/artifacts/trees/"):
            resp.json.return_value = {"tree": [{"path": "data", "type": "tree"}]}
        else:
            resp.json.return_value = {"tree": [{"path": "a.txt", "type": "blob", "size": 1}]}
        return resp

    tree.side_effect = fake_get

    ls_impl("lit://my-org/my-teamspace/data")

    assert capsys.readouterr().out.splitlines() == ["a.txt"]
    client.projects_service_get_project.assert_not_called()
    client.user_service_search_users.assert_not_called()
    assert f"/v1/projects/{TEAMSPACE_ID}/artifacts/trees/data" in tree.call_args[0][0]
