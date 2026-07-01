from unittest import mock

import pytest

from lightning_sdk.filesystem import Filesystem

TEAMSPACE_ID = "ts-123"
FAKE_TOKEN = "fake-token"
HOST = "https://lightning.ai"
REMOTE_PATH = "data/test1.txt"
LIT_URL = f"lit://my-org/my-teamspace/{REMOTE_PATH}"
LOCAL_PATH = "local/test1.txt"


@pytest.fixture()
def fake_teamspace():
    ts = mock.MagicMock()
    ts.id = TEAMSPACE_ID
    return ts


@pytest.fixture()
def fake_path_result():
    return {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": REMOTE_PATH,
    }


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_walk_yields_os_walk_style_tuples(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "tree": [
            {"path": "test-parent/test0.py", "type": "blob"},
            {"path": "test-parent/test1.py", "type": "blob"},
            {"path": "test-parent/test-sub-dir/test2.py", "type": "blob"},
            {"path": "test-parent/test3.py", "type": "blob"},
        ]
    }

    fs = Filesystem()
    result = list(fs.walk(LIT_URL))

    assert result == [
        ("test-parent", ["test-sub-dir"], ["test0.py", "test1.py", "test3.py"]),
        ("test-parent/test-sub-dir", [], ["test2.py"]),
    ]


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_walk_flat_directory(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "tree": [
            {"path": "data/a.txt", "type": "blob"},
            {"path": "data/b.txt", "type": "blob"},
        ]
    }

    fs = Filesystem()
    result = list(fs.walk(LIT_URL))

    assert result == [
        ("data", [], ["a.txt", "b.txt"]),
    ]


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_walk_empty(mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}

    fs = Filesystem()
    result = list(fs.walk(LIT_URL))

    assert result == []


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_walk_is_recursive(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}

    fs = Filesystem()
    list(fs.walk(LIT_URL))

    _, kwargs = mock_get.call_args
    assert kwargs.get("params", {}).get("recursive") in (True, "true")


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_walk_passes_correct_teamspace_id(mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get):
    mock_parse_lit_url.return_value = {"teamspace": "my-teamspace", "owner": "my-org", "destination": REMOTE_PATH}
    ts = mock.MagicMock()
    ts.id = "custom-ts-id"
    mock_resolve.return_value = ts
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}

    fs = Filesystem()
    list(fs.walk(LIT_URL))

    url = mock_get.call_args[0][0]
    assert "custom-ts-id" in url
