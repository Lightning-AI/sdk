import os
from unittest import mock

import pytest

from lightning_sdk.api.filesystem_api import FilesystemApi


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_download_file(_authenticate_mock, _mock_auth, mock_requests_get, tmpdir):
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
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_download_folder(_mock_auth, authenticate_mock, mock_executor, mock_tqdm, mock_collect, tmpdir):
    authenticate_mock.return_value = "test-token-123"
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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_download_file_rejects_an_error_document(_authenticate_mock, _mock_auth, mock_requests_get, tmp_path):
    # An object store refusing a GET answers with an XML document, not with the bytes.
    body = b"<Error><Code>InternalError</Code><Message>We encountered an internal error.</Message></Error>"
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.headers = {"content-length": str(len(body))}
    mock_response.iter_content = lambda chunk_size=None: iter([body])
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()

    filepath = tmp_path / "file1"
    with pytest.raises(RuntimeError, match="(?s)HTTP 500.*InternalError"):
        filesystem_api.download_file("file1", str(filepath), "ts-abc")

    assert list(tmp_path.iterdir()) == []


@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
def test_download_folder_does_not_report_success_on_a_partial_download(
    _mock_auth, _authenticate_mock, inline_executor_cls, tmp_path
):
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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_list_files_returns_tree(_authenticate_mock, _mock_auth, mock_requests_get):
    fake_files = [{"name": "test1.txt"}, {"name": "test2.txt"}]
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": fake_files}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    assert result == fake_files


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_list_files_returns_empty_when_tree_missing(_authenticate_mock, _mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    result = filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    assert result == []


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_list_files_passes_correct_url_and_params(_authenticate_mock, _mock_auth, mock_requests_get):
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
    assert params["token"] == "token"


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_list_files_non_recursive_by_default(_authenticate_mock, _mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tree": []}
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")

    params = mock_requests_get.call_args[1]["params"]
    assert params["recursive"] == "false"


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth")
@mock.patch("lightning_sdk.api.filesystem_api._authenticate_and_get_token", return_value="token")
def test_list_files_raises_on_non_200(_authenticate_mock, _mock_auth, mock_requests_get):
    mock_response = mock.MagicMock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    filesystem_api = FilesystemApi()
    with pytest.raises(RuntimeError, match="Failed to list files: 404"):
        filesystem_api.list_files(teamspace_id="ts-abc", path="path/to/files")
