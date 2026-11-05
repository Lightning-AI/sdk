import os
from unittest import mock

import pytest
import requests

from lightning_sdk.api.filesystem_api import FilesystemApi
from lightning_sdk.api.utils import _DOWNLOAD_MAX_TRIES, CredentialAuth


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_file(_mock_auth, mock_requests_get, tmpdir):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "0"}
    mock_response.iter_content.return_value = iter([])
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()

    filepath = os.path.join(tmpdir, "file1")
    filesystem_api.download_file("file1", filepath, "ts-abc")


@mock.patch("lightning_sdk.api.filesystem_api._collect_download_results")
@mock.patch("lightning_sdk.api.filesystem_api.tqdm")
@mock.patch("lightning_sdk.api.filesystem_api.ThreadPoolExecutor")
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_folder(_mock_auth, mock_executor, mock_tqdm, mock_collect, tmpdir):
    filesystem_api = FilesystemApi()

    filesystem_api.list_files = mock.Mock(
        return_value=[
            {"type": "blob", "path": "file1.txt", "size": 1000},
            {"type": "blob", "path": "file2.txt", "size": 2000},
        ]
    )

    filesystem_api._download_single_file = mock.Mock()

    mock_future = mock.Mock()
    mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future
    mock_collect.return_value = None

    filepath = os.path.join(tmpdir, "download_folder")
    filesystem_api.download_folder("file1", filepath, "ts-abc")

    filesystem_api.list_files.assert_called_once_with("ts-abc", "file1", recursive=True)
    mock_executor.assert_called_once()
    mock_tqdm.assert_called_once()
    assert mock_tqdm.call_args.kwargs["desc"] == "Downloading files"
    assert mock_tqdm.call_args.kwargs["total"] == 3000  # 1000 + 2000


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_file_rejects_an_error_document(_mock_auth, mock_requests_get, tmp_path):
    # An object store refusing a GET answers with an XML document, not with the bytes.
    body = b"<Error><Code>InternalError</Code><Message>We encountered an internal error.</Message></Error>"
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.headers = {"content-length": str(len(body))}
    mock_response.iter_content = lambda chunk_size=None: iter([body])
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()

    filepath = tmp_path / "file1"
    with mock.patch("time.sleep"), pytest.raises(RuntimeError, match="(?s)HTTP 500.*InternalError"):
        filesystem_api.download_file("file1", str(filepath), "ts-abc")

    # A 500 is a temporary condition, so it is retried before giving up.
    assert mock_requests_get.call_count == _DOWNLOAD_MAX_TRIES
    assert list(tmp_path.iterdir()) == []


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_file_retries_a_dropped_connection(_mock_auth, mock_requests_get, tmp_path):
    body = b"hello"
    ok_response = mock.Mock()
    ok_response.status_code = 200
    ok_response.headers = {"content-length": str(len(body))}
    ok_response.iter_content = lambda chunk_size=None: iter([body])
    mock_requests_get.side_effect = [requests.exceptions.ConnectionError("connection reset"), ok_response]

    filesystem_api = FilesystemApi()

    filepath = tmp_path / "file1"
    with mock.patch("time.sleep"):
        filesystem_api.download_file("file1", str(filepath), "ts-abc", progress_bar=False)

    assert mock_requests_get.call_count == 2
    assert filepath.read_bytes() == body


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_file_retries_a_truncated_body(_mock_auth, mock_requests_get, tmp_path):
    # A body shorter than Content-Length promised is a cut connection: retried, not fatal.
    body = b"hello"
    short_response = mock.Mock()
    short_response.status_code = 200
    short_response.headers = {"content-length": str(len(body))}
    short_response.iter_content = lambda chunk_size=None: iter([body[:2]])
    ok_response = mock.Mock()
    ok_response.status_code = 200
    ok_response.headers = {"content-length": str(len(body))}
    ok_response.iter_content = lambda chunk_size=None: iter([body])
    mock_requests_get.side_effect = [short_response, ok_response]

    filesystem_api = FilesystemApi()

    filepath = tmp_path / "file1"
    with mock.patch("time.sleep"):
        filesystem_api.download_file("file1", str(filepath), "ts-abc", progress_bar=False)

    assert mock_requests_get.call_count == 2
    assert filepath.read_bytes() == body


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_file_does_not_retry_a_denial(_mock_auth, mock_requests_get, tmp_path):
    mock_response = mock.Mock()
    mock_response.status_code = 404
    mock_response.headers = {}
    mock_response.iter_content = lambda chunk_size=None: iter([b"not found"])
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()

    with pytest.raises(RuntimeError, match="HTTP 404"):
        filesystem_api.download_file("file1", str(tmp_path / "file1"), "ts-abc")

    assert mock_requests_get.call_count == 1


@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_download_folder_does_not_report_success_on_a_partial_download(_mock_auth, inline_executor_cls, tmp_path):
    filesystem_api = FilesystemApi()
    filesystem_api.list_files = mock.Mock(
        return_value=[
            {"type": "blob", "path": "ok.bin", "size": 1000},
            {"type": "blob", "path": "single_2mib.bin", "size": 2 * 1024 * 1024},
        ]
    )

    def download(remote_path, *args, **kwargs):
        if remote_path.endswith("single_2mib.bin"):
            raise RuntimeError("Failed to download 'single_2mib.bin': HTTP 503: SlowDown")

    filesystem_api._download_single_file = mock.Mock(side_effect=download)

    with (
        mock.patch("lightning_sdk.api.filesystem_api.ThreadPoolExecutor", inline_executor_cls),
        pytest.raises(RuntimeError, match="single_2mib.bin"),
    ):
        filesystem_api.download_folder("file1", str(tmp_path), "ts-abc", progress_bar=False)


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_list_files_returns_tree(_mock_auth, mock_requests_get):
    fake_files = [{"name": "test1.txt"}, {"name": "test2.txt"}]
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": fake_files}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    assert result == fake_files


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_list_files_returns_empty_when_tree_missing(_mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    assert result == []


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_list_files_passes_correct_url_and_params(_mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": []}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files/", recursive=True)

    mock_requests_get.assert_called_once()
    url = mock_requests_get.call_args[0][0]
    params = mock_requests_get.call_args[1]["params"]

    assert "ts-abc" in url
    assert "path/to/files" in url
    assert params["recursive"] == "true"
    assert isinstance(mock_requests_get.call_args[1]["auth"], CredentialAuth)


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_list_files_non_recursive_by_default(_mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": []}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    params = mock_requests_get.call_args[1]["params"]
    assert params["recursive"] == "false"


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_list_files_raises_on_non_200(_mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    with pytest.raises(RuntimeError, match="Failed to list files: 404"):
        filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
def test_list_files_follows_cursor_pages(_mock_auth, mock_requests_get):
    """A truncated listing is followed page by page until nextCursor comes back empty."""
    pages = [
        {"tree": [{"path": "a.txt"}], "truncated": True, "nextCursor": "cursor-1"},
        {"tree": [{"path": "b.txt"}], "truncated": True, "nextCursor": "cursor-2"},
        {"tree": [{"path": "c.txt"}], "truncated": False},
    ]
    responses = []
    for page in pages:
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.json.return_value = page
        responses.append(resp)
    mock_requests_get.side_effect = responses

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="big-folder", recursive=True, page_size=1)

    assert [entry["path"] for entry in result] == ["a.txt", "b.txt", "c.txt"]

    params = [call[1]["params"] for call in mock_requests_get.call_args_list]
    assert "cursor" not in params[0]
    assert params[1]["cursor"] == "cursor-1"
    assert params[2]["cursor"] == "cursor-2"
    assert all(p["recursive"] == "true" and p["atMost"] == "1" for p in params)


@mock.patch("lightning_sdk.lightning_cloud.credentials.Auth")
@mock.patch("lightning_sdk.api.utils.LightningClient")
@mock.patch("requests.get", autospec=True)
def test_download_folder_preserves_each_file_mtime(mock_get, _mock_client, _mock_auth, tmp_path, inline_executor_cls):
    api = FilesystemApi()
    api.list_files = mock.Mock(
        return_value=[
            {"path": "first.txt", "type": "blob", "size": 4},
            {"path": "nested/second.txt", "type": "blob", "size": 4},
        ]
    )

    def download_response(url, **kwargs):
        metadata = (
            {"X-Amz-Meta-Mtime": "1700000000.123456789"}
            if url.endswith("first.txt")
            else {"Last-Modified": "Tue, 14 Nov 2023 22:13:21 GMT"}
        )
        response = requests.Response()
        response.status_code = 200
        response.headers = requests.structures.CaseInsensitiveDict({"Content-Length": "4", **metadata})
        response.iter_content = mock.Mock(return_value=iter([b"data"]))
        return response

    mock_get.side_effect = download_response
    with mock.patch("lightning_sdk.api.filesystem_api.ThreadPoolExecutor", inline_executor_cls):
        api.download_folder("data", str(tmp_path), "ts-abc", progress_bar=False)

    assert (tmp_path / "first.txt").read_bytes() == b"data"
    assert (tmp_path / "nested/second.txt").read_bytes() == b"data"
    assert (tmp_path / "first.txt").stat().st_mtime_ns == 1700000000123456789
    assert (tmp_path / "nested/second.txt").stat().st_mtime_ns == 1700000001000000000
    assert mock_get.call_count == 2
    api.list_files.assert_called_once_with("ts-abc", "data", recursive=True)
