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


def _make_fake_response(status=200, content=b"binary-data", content_length=None):
    resp = mock.MagicMock()
    resp.status_code = status
    resp.headers = {"content-length": str(content_length or len(content))}
    resp.iter_content = mock.MagicMock(return_value=[content])
    return resp


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value=FAKE_TOKEN)
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_success(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, mock_auth, fake_teamspace, fake_path_result, tmp_path
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value = _make_fake_response(content=b"test-content")

    target = str(tmp_path / "test.txt")

    fs = Filesystem()
    fs.copy(LIT_URL, target, progress_bar=False)

    mock_parse_lit_url.assert_called_once_with(LIT_URL)
    mock_resolve.assert_called_once_with("my-teamspace", "my-org")
    mock_get.assert_called_once_with(
        f"{HOST}/v1/projects/{TEAMSPACE_ID}/artifacts/blobs/{REMOTE_PATH}",
        params={"token": FAKE_TOKEN},
        stream=True,
        allow_redirects=True,
    )
    assert (tmp_path / "test.txt").read_bytes() == b"test-content"


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value=FAKE_TOKEN)
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_creates_nested_directories(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, mock_auth, fake_teamspace, fake_path_result, tmp_path
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value = _make_fake_response()

    nested_target = str(tmp_path / "a" / "b" / "c" / "test.txt")

    fs = Filesystem()
    fs.copy(LIT_URL, nested_target, progress_bar=False)

    assert (tmp_path / "a" / "b" / "c").is_dir()
    assert (tmp_path / "a" / "b" / "c" / "test.txt").exists()


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value=FAKE_TOKEN)
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_raises_on_non_200(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, mock_auth, fake_teamspace, fake_path_result, tmp_path
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value = _make_fake_response(status=404)

    fs = Filesystem()
    with pytest.raises(RuntimeError, match="Failed to download file: 404"):
        fs.copy(LIT_URL, str(tmp_path / "test.txt"), progress_bar=False)


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value=FAKE_TOKEN)
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_passes_correct_teamspace_id_in_url(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, mock_auth, tmp_path
):
    mock_parse_lit_url.return_value = {"teamspace": "my-teamspace", "owner": "my-org", "destination": REMOTE_PATH}
    ts = mock.MagicMock()
    ts.id = "custom-ts-id"
    mock_resolve.return_value = ts
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value = _make_fake_response()

    fs = Filesystem()
    fs.copy(LIT_URL, str(tmp_path / "test.txt"), progress_bar=False)

    url = mock_get.call_args[0][0]
    assert "custom-ts-id" in url


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value=FAKE_TOKEN)
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_download_passes_token_in_query_params(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, mock_auth, fake_teamspace, fake_path_result, tmp_path
):
    mock_parse_lit_url.return_value = fake_path_result
    mock_resolve.return_value = fake_teamspace
    mock_client_cls.return_value.api_client.configuration.host = HOST
    mock_get.return_value = _make_fake_response()

    fs = Filesystem()
    fs.copy(LIT_URL, str(tmp_path / "test.txt"), progress_bar=False)

    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"token": FAKE_TOKEN}
    assert kwargs["stream"] is True
    assert kwargs["allow_redirects"] is True


def test_copy_raises_when_both_paths_are_lit():
    fs = Filesystem()
    with pytest.raises(ValueError, match="Cannot copy between two remote URLs"):
        fs.copy("lit://org/ts/file.txt", "lit://org/ts/other.txt")


def test_copy_raises_when_neither_path_is_lit():
    fs = Filesystem()
    with pytest.raises(ValueError, match="At least one path must be a lit://"):
        fs.copy("local/file.txt", "other/file.txt")


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value=FAKE_TOKEN)
@mock.patch("lightning_sdk.api.filesystem_api.requests.get")
@mock.patch("lightning_sdk.api.filesystem_api.LightningClient")
@mock.patch("lightning_sdk.filesystem.filesystem.resolve_teamspace")
@mock.patch("lightning_sdk.filesystem.filesystem.parse_lit_url")
def test_copy_upload_raises_not_implemented(
    mock_parse_lit_url, mock_resolve, mock_client_cls, mock_get, mock_auth, tmp_path
):
    """Upload (local source, lit:// destination) should raise NotImplementedError."""
    fs = Filesystem()
    with pytest.raises(NotImplementedError, match="Filesystem upload is not implemented"):
        fs.copy("local/file.txt", "lit://org/ts/file.txt")
