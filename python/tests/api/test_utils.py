from unittest import mock
from unittest.mock import MagicMock, Mock, mock_open

import pytest
import requests

import lightning_sdk.api.utils
from lightning_sdk.api import utils
from lightning_sdk.api.utils import (
    _BlobUploader,
    _download_model_files,
    _download_teamspace_files,
    _FileDownloader,
    _local_file_matches_size,
    _machine_to_compute_name,
    _ModelFileUploader,
    _sanitize_studio_remote_path,
    resolve_path_mappings,
)
from lightning_sdk.lightning_cloud.openapi import (
    ModelsStoreCreateMultiPartUploadBody,
    ModelsStoreGetModelFileUploadUrlsBody,
    V1ListProjectArtifactsResponse,
    V1PathMapping,
    V1ProjectArtifact,
    V1SignedUrl,
)
from lightning_sdk.machine import Machine

_TEST_ENDPOINT_BASE = "https://api.example.com/v1/projects/test-project-id/artifacts"


def _make_mocked_blob_uploader(monkeypatch, file_path, remote_path, **kwargs):
    # Threadpools don't like mocks as input, so we just use a regular map here
    monkeypatch.setattr(lightning_sdk.api.utils.ThreadPoolExecutor, "map", map)
    monkeypatch.setattr(lightning_sdk.api.utils, "_authenticate_and_get_token", lambda client: "test-token")
    return _BlobUploader(
        client=Mock(),
        endpoint_base=_TEST_ENDPOINT_BASE,
        progress_bar=False,
        file_path=file_path,
        remote_path=remote_path,
        **kwargs,
    )


def _blob_upload_response(remote_path, upload_id, urls):
    response = Mock(status_code=200)
    response.json.return_value = {
        "expires_at": "2026-01-01T00:00:00Z",
        "results": [{"path": remote_path, "upload_id": upload_id, "urls": urls}],
    }
    return response


def test_blob_uploader_path_exists(monkeypatch):
    with pytest.raises(FileNotFoundError):
        _make_mocked_blob_uploader(monkeypatch, file_path="not-exist", remote_path="any")


@pytest.mark.parametrize(
    ("machine", "compute_name"),
    [
        (Machine.CPU, "cpu-4"),
        (Machine.L40S_X_8, "lit-l40s-8"),
        ("trn1.2xlarge", "trn1.2xlarge"),
    ],
)
def test_machine_to_compute_name(machine, compute_name):
    assert _machine_to_compute_name(machine) == compute_name


def test_blob_uploader_multipart(tmp_path, monkeypatch):
    """A file above the multipart threshold requests part URLs, PUTs each part, and completes."""
    monkeypatch.setenv("LIGHTNING_MULTIPART_THRESHOLD", "4")
    monkeypatch.setenv("LIGHTNING_MULTI_PART_PART_SIZE", "4")

    file_path = tmp_path / "file"
    file_path.write_bytes(b"0123456789")  # 3 parts of 4 bytes

    uploader = _make_mocked_blob_uploader(
        monkeypatch, file_path=str(file_path), remote_path="path/to/file/on/remote", cluster_id="test-cluster-id"
    )

    post_mock = Mock(
        side_effect=[
            _blob_upload_response(
                "path/to/file/on/remote",
                "test-upload-id",
                [
                    {"url": "test-url-1", "part_number": 1},
                    {"url": "test-url-2", "part_number": 2},
                    {"url": "test-url-3", "part_number": 3},
                ],
            ),
            Mock(status_code=204),
        ]
    )
    put_mock = Mock(return_value=Mock(status_code=200, headers={"ETag": "test-etag"}))
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "post", post_mock)
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "put", put_mock)

    uploader.progress_bar = Mock()
    uploader()

    create_call = post_mock.call_args_list[0]
    assert create_call.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs"
    assert create_call.kwargs["params"] == {"token": "test-token"}
    assert create_call.kwargs["json"] == {
        "cluster_id": "test-cluster-id",
        "blobs": [{"path": "path/to/file/on/remote", "parts": 3, "part_size": 4}],
    }

    assert [c.args[0] for c in put_mock.call_args_list] == ["test-url-1", "test-url-2", "test-url-3"]
    assert [c.kwargs["data"] for c in put_mock.call_args_list] == [b"0123", b"4567", b"89"]

    complete_call = post_mock.call_args_list[1]
    assert complete_call.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs/complete"
    assert complete_call.kwargs["json"] == {
        "cluster_id": "test-cluster-id",
        "blobs": [
            {
                "path": "path/to/file/on/remote",
                "upload_id": "test-upload-id",
                "parts": [
                    {"part_number": 1, "etag": "test-etag"},
                    {"part_number": 2, "etag": "test-etag"},
                    {"part_number": 3, "etag": "test-etag"},
                ],
            }
        ],
    }

    assert uploader.progress_bar.update.call_args_list == [mock.call(4), mock.call(4), mock.call(2)]


def test_blob_uploader_multipart_resigns_failed_part(tmp_path, monkeypatch):
    """A failed part PUT re-requests that part's URL (upload_id + part_numbers) and retries."""
    monkeypatch.setenv("LIGHTNING_MULTIPART_THRESHOLD", "4")
    monkeypatch.setenv("LIGHTNING_MULTI_PART_PART_SIZE", "4")

    file_path = tmp_path / "file"
    file_path.write_bytes(b"01234567")  # 2 parts of 4 bytes

    uploader = _make_mocked_blob_uploader(
        monkeypatch, file_path=str(file_path), remote_path="remote-path", cluster_id="test-cluster-id"
    )

    post_mock = Mock(
        side_effect=[
            _blob_upload_response(
                "remote-path",
                "test-upload-id",
                [{"url": "test-url-1", "part_number": 1}, {"url": "test-url-2", "part_number": 2}],
            ),
            _blob_upload_response("remote-path", "test-upload-id", [{"url": "test-url-2b", "part_number": 2}]),
            Mock(status_code=204),
        ]
    )
    failed_put = Mock(status_code=500, headers={})
    failed_put.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    ok_put = Mock(status_code=200, headers={"ETag": "test-etag"})
    put_mock = Mock(side_effect=[ok_put, failed_put, ok_put])
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "post", post_mock)
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "put", put_mock)

    uploader()

    resign_call = post_mock.call_args_list[1]
    assert resign_call.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs"
    assert resign_call.kwargs["json"] == {
        "cluster_id": "test-cluster-id",
        "blobs": [{"path": "remote-path", "upload_id": "test-upload-id", "part_numbers": [2]}],
    }
    assert [c.args[0] for c in put_mock.call_args_list] == ["test-url-1", "test-url-2", "test-url-2b"]

    complete_call = post_mock.call_args_list[2]
    assert complete_call.kwargs["json"]["blobs"][0]["parts"] == [
        {"part_number": 1, "etag": "test-etag"},
        {"part_number": 2, "etag": "test-etag"},
    ]


def test_blob_uploader_single_part(tmp_path, monkeypatch):
    """A small file gets one presigned PUT; completion only fires when notify_completion is set."""
    file_path = tmp_path / "file"
    file_path.write_bytes(b"0123")

    uploader = _make_mocked_blob_uploader(
        monkeypatch,
        file_path=str(file_path),
        remote_path="remote-path",
        content_type="text/plain",
        notify_completion=True,
    )

    post_mock = Mock(
        side_effect=[
            _blob_upload_response(
                "remote-path", "", [{"url": "signed-put-url", "headers": {"Content-Type": "text/plain"}}]
            ),
            Mock(status_code=204),
        ]
    )
    put_mock = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "post", post_mock)
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "put", put_mock)

    uploader()

    create_call = post_mock.call_args_list[0]
    assert create_call.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs"
    # no cluster_id (e.g. studio and lightning_storage scopes), single-part has no "parts"
    assert create_call.kwargs["json"] == {"blobs": [{"path": "remote-path", "content_type": "text/plain"}]}

    put_call = put_mock.call_args_list[0]
    assert put_call.args[0] == "signed-put-url"
    assert put_call.kwargs["headers"] == {"Content-Type": "text/plain"}

    complete_call = post_mock.call_args_list[1]
    assert complete_call.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs/complete"
    assert complete_call.kwargs["json"] == {"blobs": [{"path": "remote-path"}]}


def test_blob_uploader_single_part_no_completion(tmp_path, monkeypatch):
    """Without notify_completion, a single-part upload never calls the complete route."""
    file_path = tmp_path / "file"
    file_path.write_bytes(b"0123")

    uploader = _make_mocked_blob_uploader(
        monkeypatch, file_path=str(file_path), remote_path="remote-path", cluster_id="test-cluster-id"
    )

    post_mock = Mock(return_value=_blob_upload_response("remote-path", "", [{"url": "signed-put-url"}]))
    put_mock = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "post", post_mock)
    monkeypatch.setattr(lightning_sdk.api.utils.requests, "put", put_mock)

    uploader()

    assert post_mock.call_count == 1
    assert post_mock.call_args.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs"
    put_mock.assert_called_once()


def _make_mocked_model_uploader(monkeypatch, file_path, remote_path):
    # Threadpools don't like mocks as input, so we just use a regular map here
    monkeypatch.setattr(lightning_sdk.api.utils.ThreadPoolExecutor, "map", map)
    return _ModelFileUploader(
        client=Mock(),
        model_id="test-model-id",
        version="test-version",
        teamspace_id="test-project-id",
        progress_bar=False,
        file_path=file_path,
        remote_path=remote_path,
    )


def test_model_file_uploader_path_exists(monkeypatch):
    with pytest.raises(FileNotFoundError):
        _make_mocked_model_uploader(monkeypatch, file_path="not-exist", remote_path="any")


@mock.patch("lightning_sdk.api.utils.requests")
def test_model_file_uploader(_, tmp_path, monkeypatch):
    """Tests the basic calls that uploader makes to model store API."""
    file_path = tmp_path / "file"
    file_path.touch()
    uploader = _make_mocked_model_uploader(monkeypatch, file_path=file_path, remote_path="path/to/file/on/remote")

    uploader.progress_bar = Mock()
    uploader.client.models_store_create_multi_part_upload.return_value = Mock(upload_id="test-upload-id")
    uploader.client.models_store_get_model_file_upload_urls.return_value = Mock(
        urls=[
            V1SignedUrl(url="test-url-1", part_number=1),
            V1SignedUrl(url="test-url-2", part_number=2),
        ]
    )
    uploader.client.models_store_complete_multi_part_upload = Mock()

    uploader()

    uploader.client.models_store_create_multi_part_upload.assert_called_once_with(
        ModelsStoreCreateMultiPartUploadBody(filepath="path/to/file/on/remote"),
        model_id="test-model-id",
        project_id="test-project-id",
        version="test-version",
    )
    uploader.client.models_store_get_model_file_upload_urls.assert_called_once_with(
        ModelsStoreGetModelFileUploadUrlsBody(filepath="path/to/file/on/remote", parts=[1]),
        model_id="test-model-id",
        project_id="test-project-id",
        version="test-version",
        upload_id="test-upload-id",
    )
    uploader.client.models_store_complete_multi_part_upload.assert_called_once()

    # 0 because mocked data has length 0
    assert uploader.progress_bar.update.call_args_list == [mock.call(0), mock.call(0)]


@mock.patch("lightning_sdk.api.utils._FileDownloader")
@mock.patch("lightning_sdk.api.utils.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.utils.concurrent.futures.wait")
def test_download_model_files(wait_mock, executor_mock, file_downloader_mock, tmp_path, monkeypatch):
    tqdm_mock = MagicMock()
    monkeypatch.setattr(utils, "tqdm", tqdm_mock)
    client = Mock()

    mock_file1 = Mock(filepath="path/to/file1", url="http://a/b", size_bytes="5")
    mock_file2 = Mock(filepath="path/to/file2", url="http://c/d", size_bytes="5")

    client.models_store_get_model_files.return_value = Mock(
        model_id="test-model-id",
        project_id="test-project-id",
        version="latest",
        files=[mock_file1, mock_file2],
        filepaths=["path/to/file1", "path/to/file2"],
        size_bytes=10,
    )

    _download_model_files(
        client=client,
        teamspace_name="test-project",
        teamspace_owner_name="test-user",
        name="modelname",
        version="latest",
        download_dir=tmp_path,
        progress_bar=True,
    )

    client.models_store_get_model_files.assert_called_once_with(
        project_name="test-project", project_owner_name="test-user", name="modelname", version="latest"
    )

    assert tqdm_mock._mock_mock_calls[0].kwargs == {
        "desc": "Downloading latest",
        "unit": "B",
        "total": 10.0,
        "unit_scale": True,
        "unit_divisor": 1000,
        "position": -1,
        "mininterval": 1,
    }
    assert file_downloader_mock.call_count == 2
    assert wait_mock.call_count == 1

    # By default, skip_if_exists is forwarded as True to every _FileDownloader instantiation
    for call in file_downloader_mock.call_args_list:
        assert call.kwargs["skip_if_exists"] is True


@mock.patch("lightning_sdk.api.utils._FileDownloader")
@mock.patch("lightning_sdk.api.utils.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.utils.concurrent.futures.wait")
def test_download_model_files_forwards_skip_if_exists_false(
    wait_mock, executor_mock, file_downloader_mock, tmp_path, monkeypatch
):
    tqdm_mock = MagicMock()
    monkeypatch.setattr(utils, "tqdm", tqdm_mock)
    client = Mock()

    client.models_store_get_model_files.return_value = Mock(
        model_id="test-model-id",
        project_id="test-project-id",
        version="latest",
        files=[],
        filepaths=["path/to/file1"],
        size_bytes=5,
    )

    _download_model_files(
        client=client,
        teamspace_name="test-project",
        teamspace_owner_name="test-user",
        name="modelname",
        version="latest",
        download_dir=tmp_path,
        progress_bar=False,
        skip_if_exists=False,
    )

    assert file_downloader_mock.call_count == 1
    assert file_downloader_mock.call_args.kwargs["skip_if_exists"] is False


@mock.patch("lightning_sdk.api.utils._FileDownloader")
@mock.patch("lightning_sdk.api.utils.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.utils.concurrent.futures.wait")
def test_download_teamspace_files(wait_mock, executor_mock, file_downloader_mock, tmp_path, monkeypatch):
    tqdm_mock = MagicMock()
    monkeypatch.setattr(utils, "tqdm", tqdm_mock)
    client = Mock()

    client.storage_service_list_project_artifacts.return_value = V1ListProjectArtifactsResponse(
        artifacts=[
            V1ProjectArtifact(filename="file1", url="http://example.com/file1", size_bytes="10"),
            V1ProjectArtifact(filename="file2", url="http://example.com/file2", size_bytes="20"),
        ],
        next_page_token="",
    )

    _download_teamspace_files(
        client=client,
        teamspace_id="test-project-id",
        cluster_id="test-cluster-id",
        prefix="test-prefix",
        download_dir=tmp_path,
        progress_bar=True,
    )

    client.storage_service_list_project_artifacts.assert_called_once_with(
        project_id="test-project-id",
        cluster_id="test-cluster-id",
        page_token="",
        include_download_url=True,
        prefix="test-prefix",
        page_size=1000,
    )

    assert file_downloader_mock.call_count == 2
    assert wait_mock.call_count == 1

    # By default, skip_if_exists is forwarded as True to every _FileDownloader instantiation
    for call in file_downloader_mock.call_args_list:
        assert call.kwargs["skip_if_exists"] is True


@mock.patch("lightning_sdk.api.utils._FileDownloader")
@mock.patch("lightning_sdk.api.utils.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.utils.concurrent.futures.wait")
def test_download_teamspace_files_forwards_skip_if_exists_false(
    wait_mock, executor_mock, file_downloader_mock, tmp_path, monkeypatch
):
    tqdm_mock = MagicMock()
    monkeypatch.setattr(utils, "tqdm", tqdm_mock)
    client = Mock()

    client.storage_service_list_project_artifacts.return_value = V1ListProjectArtifactsResponse(
        artifacts=[V1ProjectArtifact(filename="file1", url="http://example.com/file1", size_bytes="10")],
        next_page_token="",
    )

    _download_teamspace_files(
        client=client,
        teamspace_id="test-project-id",
        cluster_id="test-cluster-id",
        prefix="test-prefix",
        download_dir=tmp_path,
        progress_bar=True,
        skip_if_exists=False,
    )

    assert file_downloader_mock.call_count == 1
    assert file_downloader_mock.call_args.kwargs["skip_if_exists"] is False


def mock_iter_content(chunk_size):
    chunks = [b"test_data"]
    yield from chunks


@mock.patch("requests.get")
def test_download_chunk_success(mock_get):
    url = "http://example.com"
    start = 0
    end = 100
    filename = "test_file"

    mock_response = Mock()
    mock_response.status_code = 206
    mock_response.iter_content = mock_iter_content

    mock_get.return_value.__enter__.return_value = mock_response

    file_downloader = _FileDownloader(
        teamspace_id="bar",
        remote_path="some",
        file_path=filename,
        num_workers=1,
        progress_bar=None,
        executor=Mock(),
        url=url,
        size=101,
        refresh_fn=Mock(),
    )

    with mock.patch("builtins.open", mock_open()) as mock_file:
        file_downloader._download_chunk(filename, (start, end))

        mock_get.assert_called_once_with(url, headers={"Range": "bytes=0-100"}, stream=True)

        mock_file.assert_called_once_with(filename, "r+b")
        mock_file().seek.assert_called_once_with(start)
        mock_file().write.assert_called_once_with(b"test_data")


@mock.patch("time.sleep", return_value=None)
@mock.patch("requests.get")
def test_download_chunk_failure_and_retry_success(mock_get, _):
    url = "http://example.com"
    start = 0
    end = 100
    filename = "test_file"

    # First call fails
    mock_response_fail = Mock()
    mock_response_fail.status_code = 403
    mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_fail)

    # Second call succeeds
    mock_response_success = Mock()
    mock_response_success.status_code = 206
    mock_response_success.iter_content = mock_iter_content

    # mock_get will return fail then success
    mock_get.return_value.__enter__.side_effect = [mock_response_fail, mock_response_success]

    new_url = "http://new.example.com"
    refresh_fn_mock = Mock(return_value={"url": new_url, "size": 101})

    file_downloader = _FileDownloader(
        teamspace_id="bar",
        remote_path="some",
        file_path=filename,
        num_workers=1,
        progress_bar=None,
        executor=Mock(),
        url=url,
        size=101,
        refresh_fn=refresh_fn_mock,
    )

    with mock.patch("builtins.open", mock_open()):
        # This should not raise an exception because the retry will succeed
        file_downloader._download_chunk(filename, (start, end))

    # Check calls
    assert mock_get.call_count == 2
    # First call with old url
    mock_get.assert_any_call(url, headers={"Range": "bytes=0-100"}, stream=True)
    # Second call with new url from refresh_fn
    mock_get.assert_any_call(new_url, headers={"Range": "bytes=0-100"}, stream=True)

    assert refresh_fn_mock.call_count == 1


# ---------------------------------------------------------------------------
# Tests for the skip-if-exists optimization on downloads
# ---------------------------------------------------------------------------


class TestLocalFileMatchesSize:
    """Tests for the _local_file_matches_size helper."""

    def test_returns_false_when_expected_size_is_none(self, tmp_path):
        f = tmp_path / "file"
        f.write_bytes(b"hello")
        assert _local_file_matches_size(str(f), None) is False

    def test_returns_false_when_file_missing(self, tmp_path):
        assert _local_file_matches_size(str(tmp_path / "missing"), 10) is False

    def test_returns_false_when_size_mismatch(self, tmp_path):
        f = tmp_path / "file"
        f.write_bytes(b"hello")  # 5 bytes
        assert _local_file_matches_size(str(f), 10) is False

    def test_returns_true_when_size_matches(self, tmp_path):
        f = tmp_path / "file"
        f.write_bytes(b"hello")  # 5 bytes
        assert _local_file_matches_size(str(f), 5) is True

    def test_returns_true_when_expected_size_is_string(self, tmp_path):
        # The artifact API returns size_bytes as a string; helper must coerce it.
        f = tmp_path / "file"
        f.write_bytes(b"hello")
        assert _local_file_matches_size(str(f), "5") is True

    def test_returns_false_on_directory(self, tmp_path):
        # A directory is not a regular file, even if some size could be computed.
        assert _local_file_matches_size(str(tmp_path), 0) is False


def _make_file_downloader(file_path, size=None, url=None, refresh_fn=None, skip_if_exists=True, progress_bar=None):
    return _FileDownloader(
        teamspace_id="ts",
        remote_path="remote/path",
        file_path=str(file_path),
        num_workers=1,
        progress_bar=progress_bar,
        executor=Mock(),
        url=url,
        size=size,
        refresh_fn=refresh_fn,
        skip_if_exists=skip_if_exists,
    )


def test_downloader_skips_when_local_file_matches_size(tmp_path):
    """If size is known up-front and local file matches, no network nor refresh should happen."""
    local = tmp_path / "file"
    local.write_bytes(b"hello")  # 5 bytes

    refresh_fn = Mock()
    progress_bar = Mock()
    downloader = _make_file_downloader(
        local,
        size=5,
        url="http://example.com/file",
        refresh_fn=refresh_fn,
        progress_bar=progress_bar,
    )

    with mock.patch.object(downloader, "_create_empty_file") as create_mock, mock.patch.object(
        downloader, "_multipart_download"
    ) as multipart_mock:
        downloader.download()

    # No file was (re)created, no download happened, refresh wasn't called.
    create_mock.assert_not_called()
    multipart_mock.assert_not_called()
    refresh_fn.assert_not_called()
    # Progress bar advanced by the skipped size so totals stay correct.
    progress_bar.update.assert_called_once_with(5)


def test_downloader_skips_after_refresh_when_size_only_known_post_refresh(tmp_path):
    """For the model-files flow, size is only known after refresh(); we should still skip."""
    local = tmp_path / "file"
    local.write_bytes(b"hello")  # 5 bytes

    # url is None initially -> downloader must call refresh() first.
    refresh_fn = Mock(return_value={"url": "http://example.com/file", "size": 5})
    downloader = _make_file_downloader(local, size=None, url=None, refresh_fn=refresh_fn)

    with mock.patch.object(downloader, "_create_empty_file") as create_mock, mock.patch.object(
        downloader, "_multipart_download"
    ) as multipart_mock:
        downloader.download()

    refresh_fn.assert_called_once()
    create_mock.assert_not_called()
    multipart_mock.assert_not_called()


def test_downloader_does_not_skip_when_size_mismatches(tmp_path):
    """If the local file exists but has the wrong size, the download must proceed."""
    local = tmp_path / "file"
    local.write_bytes(b"hi")  # 2 bytes, expected 5

    downloader = _make_file_downloader(local, size=5, url="http://example.com/file")

    with mock.patch.object(downloader, "_create_empty_file") as create_mock, mock.patch.object(
        downloader, "_multipart_download"
    ) as multipart_mock, mock.patch("lightning_sdk.api.utils.os.rename") as rename_mock:
        downloader.download()

    create_mock.assert_called_once()
    multipart_mock.assert_called_once()
    rename_mock.assert_called_once()


def test_downloader_does_not_skip_when_local_file_missing(tmp_path):
    """If the local file does not exist, the download must proceed even if skip_if_exists=True."""
    local = tmp_path / "does_not_exist"

    downloader = _make_file_downloader(local, size=5, url="http://example.com/file")

    with mock.patch.object(downloader, "_create_empty_file") as create_mock, mock.patch.object(
        downloader, "_multipart_download"
    ) as multipart_mock, mock.patch("lightning_sdk.api.utils.os.rename"):
        downloader.download()

    create_mock.assert_called_once()
    multipart_mock.assert_called_once()


def test_downloader_skip_if_exists_false_forces_download(tmp_path):
    """With skip_if_exists=False, a matching local file must NOT short-circuit the download."""
    local = tmp_path / "file"
    local.write_bytes(b"hello")  # 5 bytes, matches expected

    downloader = _make_file_downloader(local, size=5, url="http://example.com/file", skip_if_exists=False)

    with mock.patch.object(downloader, "_create_empty_file") as create_mock, mock.patch.object(
        downloader, "_multipart_download"
    ) as multipart_mock, mock.patch("lightning_sdk.api.utils.os.rename") as rename_mock:
        downloader.download()

    create_mock.assert_called_once()
    multipart_mock.assert_called_once()
    rename_mock.assert_called_once()


def test_downloader_skip_does_not_touch_progress_bar_when_none(tmp_path):
    """The skip path must be safe when no progress bar is attached."""
    local = tmp_path / "file"
    local.write_bytes(b"hello")

    downloader = _make_file_downloader(local, size=5, url="http://example.com/file", progress_bar=None)

    # Should simply return without raising.
    downloader.download()


def test_resolve_path_mappings():
    assert len(resolve_path_mappings({})) == 0

    path_mappings = resolve_path_mappings({"/output": "some-connection:some-path"})
    assert len(path_mappings) == 1
    assert isinstance(path_mappings[0], V1PathMapping)
    assert path_mappings[0].container_path == "/output"
    assert path_mappings[0].connection_name == "some-connection"
    assert path_mappings[0].connection_path == "some-path"

    path_mappings = resolve_path_mappings(
        {
            "/path1": "conn1:remotepath1",
            "/path2": "conn2",
        }
    )

    assert len(path_mappings) == 2
    assert all(isinstance(x, V1PathMapping) for x in path_mappings)

    assert path_mappings[0].container_path == "/path1"
    assert path_mappings[0].connection_name == "conn1"
    assert path_mappings[0].connection_path == "remotepath1"

    assert path_mappings[1].container_path == "/path2"
    assert path_mappings[1].connection_name == "conn2"
    assert path_mappings[1].connection_path == ""


def test_sanitize_studio_remote_path():
    path = "test-folder"
    studio_id = "test-studio-id"
    result = _sanitize_studio_remote_path(path, studio_id)
    assert result == f"/cloudspaces/{studio_id}/code/content/{path}"

    path = "test-folder/sub-folder"
    result = _sanitize_studio_remote_path(path, studio_id)
    assert result == f"/cloudspaces/{studio_id}/code/content/{path}"

    path = ""
    result = _sanitize_studio_remote_path(path, studio_id)
    assert result == f"/cloudspaces/{studio_id}/code/content/"


def _make_single_part_blob_uploader(tmp_path, progress_bar=False, notify_completion=False, extra_headers=None):
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("hello world")
    with mock.patch("lightning_sdk.api.utils._authenticate_and_get_token", return_value="test-token"):
        return utils._BlobUploader(
            client=Mock(),
            endpoint_base=_TEST_ENDPOINT_BASE,
            file_path=str(file_path),
            remote_path="test_file.txt",
            progress_bar=progress_bar,
            extra_headers=extra_headers,
            notify_completion=notify_completion,
        )


def _configure_single_part_create(mock_requests, url="http://example.com/upload", headers=None):
    mock_requests.post.return_value = _blob_upload_response("test_file.txt", "", [{"url": url, "headers": headers}])


@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_basic(mock_requests, tmp_path):
    uploader = _make_single_part_blob_uploader(tmp_path)
    _configure_single_part_create(mock_requests)

    mock_requests.put.return_value = Mock(status_code=200)

    uploader()

    # one URL request against the batch endpoint, authenticated via token param
    assert mock_requests.post.call_count == 1
    post_call = mock_requests.post.call_args
    assert post_call.args[0] == f"{_TEST_ENDPOINT_BASE}/blobs"
    assert post_call.kwargs["params"] == {"token": "test-token"}

    # one PUT straight to the signed storage URL, with no token
    assert mock_requests.put.call_count == 1
    call = mock_requests.put.call_args
    assert call.args[0] == "http://example.com/upload"
    assert "params" not in call.kwargs
    assert call.kwargs["timeout"] == 30
    assert call.kwargs["headers"] is None


@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_with_progress_bar(mock_requests, tmp_path):
    uploader = _make_single_part_blob_uploader(tmp_path, progress_bar=True)
    _configure_single_part_create(mock_requests)

    mock_requests.put.return_value = Mock(status_code=200)

    uploader()

    assert mock_requests.put.call_count == 1
    call = mock_requests.put.call_args
    # Body should be wrapped in _IterableFileWrapper when progress_bar=True
    assert isinstance(call.kwargs["data"], utils._IterableFileWrapper)


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_retries_on_http_error(mock_requests, _, tmp_path):
    uploader = _make_single_part_blob_uploader(tmp_path)
    _configure_single_part_create(mock_requests)

    mock_requests.put.side_effect = [
        requests.exceptions.RequestException(),
        Mock(status_code=200),
    ]

    uploader()

    assert mock_requests.put.call_count == 2
    # each attempt requests a fresh signed URL
    assert mock_requests.post.call_count == 2


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_retries_on_transient_status(mock_requests, _, tmp_path):
    uploader = _make_single_part_blob_uploader(tmp_path)
    _configure_single_part_create(mock_requests)

    # A transient 503 must be retried rather than failing immediately.
    mock_requests.put.side_effect = [
        Mock(status_code=503),
        Mock(status_code=200),
    ]

    uploader()

    assert mock_requests.put.call_count == 2


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_retries_auth_errors_with_fresh_url(mock_requests, _, tmp_path):
    uploader = _make_single_part_blob_uploader(tmp_path)
    _configure_single_part_create(mock_requests)

    # Storage 401/403 must be retried: fresh credentials can lag right after a
    # lightning_storage folder is created, and each retry signs a fresh URL.
    mock_requests.put.side_effect = [
        Mock(status_code=401),
        Mock(status_code=200),
    ]

    uploader()

    assert mock_requests.put.call_count == 2
    # each attempt requested a freshly signed URL
    assert mock_requests.post.call_count == 2


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_does_not_retry_client_error(mock_requests, _, tmp_path):
    uploader = _make_single_part_blob_uploader(tmp_path)
    _configure_single_part_create(mock_requests)

    # A non-transient 4xx should fail immediately without retrying.
    mock_requests.put.return_value = Mock(status_code=404)

    with pytest.raises(RuntimeError, match="Failed to upload file"):
        uploader()

    assert mock_requests.put.call_count == 1
