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
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_listdir_returns_files(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST

    fake_files = [{"path": "test1.txt", "size": 1024}, {"path": "test2.txt", "size": 256}]
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": fake_files}

    fs = Filesystem()
    result = fs.listdir(LIT_URL)

    mock_parse_lit_url.assert_called_once_with(LIT_URL)
    mock_resolve.assert_called_once_with("my-teamspace", "my-org")
    assert result == ["test1.txt", "test2.txt"]


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_listdir_passes_correct_teamspace_id(mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get):
    mock_parse_lit_url.return_value = {"teamspace": "my-teamspace", "owner": "my-org", "destination": REMOTE_PATH}
    ts = mock.MagicMock()
    ts.id = "custom-ts-id"
    mock_resolve.return_value = ts
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}

    fs = Filesystem()
    fs.listdir(LIT_URL)

    url = mock_get.call_args[0][0]
    assert "custom-ts-id" in url


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", new=mock.MagicMock(return_value=FAKE_TOKEN))
@mock.patch("lightning_sdk.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.parse_lit_url")
def test_listdir_non_recursive(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}

    fs = Filesystem()
    fs.listdir(LIT_URL)

    _, kwargs = mock_get.call_args
    recursive = kwargs.get("params", {}).get("recursive", False)
    assert recursive in (False, "false")
