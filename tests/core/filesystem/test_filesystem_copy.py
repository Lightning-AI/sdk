from unittest import mock

import pytest

from lightning_sdk.filesystem import Filesystem

TEAMSPACE_ID = "ts-123"
FAKE_TOKEN = "fake-token"
HOST = "https://lightning.ai"
REMOTE_PATH = "data/model.ckpt"
LIT_URL = f"lit://my-org/my-teamspace/{REMOTE_PATH}"
LOCAL_PATH = "local/model.ckpt"


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
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_file(
    mock_parse_lit_url, mock_resolve, mock_authenticate, mock_client_cls, mock_get, fake_teamspace
):
    remote_path = "data/model.ckpt"
    mock_parse_lit_url.return_value = {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": remote_path,
    }
    mock_resolve.return_value = fake_teamspace
    mock_authenticate.return_value = FAKE_TOKEN
    mock_client_cls.return_value.api_client.configuration.host = HOST

    def fake_get(url, **kwargs):
        resp = mock.MagicMock()
        resp.status_code = 200
        if "trees" in url:
            resp.json.return_value = {"tree": [{"path": "data/model.ckpt", "type": "blob", "size": 1024}]}
        else:
            resp.headers = {"content-length": "1024"}
            resp.iter_content.side_effect = lambda *a, **kw: iter([b"x" * 1024])
        return resp

    mock_get.side_effect = fake_get

    fs = Filesystem()
    fs.copy(LIT_URL, LOCAL_PATH)

    calls = [c[0][0] for c in mock_get.call_args_list]
    assert any("blobs" in url for url in calls)


@mock.patch("lightning_sdk.api.filesystem_api.concurrent.futures.wait")
@mock.patch("lightning_sdk.api.filesystem_api.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_folder(
    mock_parse_lit_url,
    mock_resolve,
    mock_authenticate,
    mock_client_cls,
    mock_get,
    mock_executor,
    mock_wait,
    fake_teamspace,
):
    mock_parse_lit_url.return_value = {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": "data/mydir",
    }
    mock_resolve.return_value = fake_teamspace
    mock_authenticate.return_value = FAKE_TOKEN
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_wait.return_value = None

    def fake_get(url, **kwargs):
        resp = mock.MagicMock()
        resp.status_code = 200
        params = kwargs.get("params", {})
        if params.get("recursive") == "true":
            resp.json.return_value = {"tree": [{"path": "file1.txt", "type": "blob", "size": 500}]}
        else:
            resp.json.return_value = {"tree": [{"path": "data/mydir", "type": "tree", "size": 0}]}
        return resp

    mock_get.side_effect = fake_get

    fs = Filesystem()
    fs.copy("lit://my-org/my-teamspace/data/mydir", "/tmp/local_out", recursive=True)

    mock_executor.assert_called_once()
    mock_executor.return_value.__enter__.return_value.submit.assert_called()


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_raises_if_directory_without_recursive(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace
):
    mock_parse_lit_url.return_value = {
        "teamspace": "my-teamspace",
        "owner": "my-org",
        "destination": "data/mydir",
    }
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": [{"path": "mydir", "type": "tree", "size": 0}]}

    fs = Filesystem()
    with pytest.raises(ValueError, match="recursive=True"):
        fs.copy("lit://my-org/my-teamspace/data/mydir", "/tmp/local_out", recursive=False)


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_raises_if_remote_file_not_found(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"tree": []}  # empty listing

    fs = Filesystem()
    with pytest.raises(ValueError, match="does not exist"):
        fs.copy(LIT_URL, LOCAL_PATH)


def test_copy_raises_if_both_remote():
    fs = Filesystem.__new__(Filesystem)
    with pytest.raises(ValueError, match="two remote URLs"):
        fs.copy("lit://org/ts/file.txt", "lit://org/ts/other.txt")


def test_copy_raises_if_both_local():
    fs = Filesystem.__new__(Filesystem)
    with pytest.raises(ValueError, match="At least one path"):
        fs.copy("/local/a.txt", "/local/b.txt")


@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_upload_raises_not_implemented(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, fake_teamspace, fake_path_result
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST

    fs = Filesystem()
    with pytest.raises(NotImplementedError):
        fs.copy(LOCAL_PATH, LIT_URL)
