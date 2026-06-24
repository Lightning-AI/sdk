import re
from unittest import mock
from unittest.mock import MagicMock, Mock, mock_open

import pytest
import requests

import lightning_sdk.api.utils
from lightning_sdk.api import utils
from lightning_sdk.api.utils import (
    _download_model_files,
    _download_teamspace_files,
    _FileDownloader,
    _FileUploader,
    _local_file_matches_size,
    _machine_to_compute_name,
    _ModelFileUploader,
    _sanitize_studio_remote_path,
    resolve_path_mappings,
)
from lightning_sdk.lightning_cloud.openapi import (
    ModelsStoreCreateMultiPartUploadBody,
    ModelsStoreGetModelFileUploadUrlsBody,
    StorageServiceCompleteUploadProjectArtifactBody,
    StorageServiceUploadProjectArtifactBody,
    StorageServiceUploadProjectArtifactPartsBody,
    V1ListProjectArtifactsResponse,
    V1PathMapping,
    V1PresignedUrl,
    V1ProjectArtifact,
    V1SignedUrl,
    V1UploadProjectArtifactPartsResponse,
)
from lightning_sdk.machine import Machine


def _make_mocked_file_uploader(monkeypatch, file_path, remote_path, data_connection_id=None):
    # Threadpools don't like mocks as input, so we just use a regular map here
    monkeypatch.setattr(lightning_sdk.api.utils.ThreadPoolExecutor, "map", map)
    return _FileUploader(
        client=Mock(),
        teamspace_id="test-project-id",
        cloud_account="test-cluster-id",
        data_connection_id=data_connection_id,
        progress_bar=False,
        file_path=file_path,
        remote_path=remote_path,
    )


def test_file_uploader_path_exists(monkeypatch):
    with pytest.raises(FileNotFoundError):
        _make_mocked_file_uploader(monkeypatch, file_path="not-exist", remote_path="any")


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


@mock.patch("lightning_sdk.api.utils.requests")
def test_file_uploader(_, tmp_path, monkeypatch):
    """Tests the basic calls that uploader makes to model store API."""
    file_path = tmp_path / "file"
    file_path.touch()
    uploader = _make_mocked_file_uploader(monkeypatch, file_path=file_path, remote_path="path/to/file/on/remote")

    uploader.progress_bar = Mock()

    uploader.client.storage_service_upload_project_artifact.return_value = Mock(upload_id="test-upload-id")
    uploader.client.storage_service_upload_project_artifact_parts.return_value = V1UploadProjectArtifactPartsResponse(
        urls=[
            V1PresignedUrl(url="test-url-1", part_number=1),
            V1PresignedUrl(url="test-url-2", part_number=2),
        ]
    )

    uploader.client.storage_service_complete_upload_project_artifact = Mock()

    uploader()

    uploader.client.storage_service_upload_project_artifact.assert_called_once_with(
        body=StorageServiceUploadProjectArtifactBody(filename="path/to/file/on/remote", cluster_id="test-cluster-id"),
        project_id="test-project-id",
    )
    uploader.client.storage_service_upload_project_artifact_parts.assert_called_once_with(
        StorageServiceUploadProjectArtifactPartsBody(
            filename="path/to/file/on/remote", parts=[1], cluster_id="test-cluster-id"
        ),
        "test-project-id",
        "test-upload-id",
    )
    uploader.client.storage_service_complete_upload_project_artifact.assert_called_once()

    # 0 because mocked data has length 0
    assert uploader.progress_bar.update.call_args_list == [mock.call(0), mock.call(0)]


@mock.patch("lightning_sdk.api.utils.requests")
def test_file_uploader_includes_data_connection_id(_, tmp_path, monkeypatch):
    file_path = tmp_path / "file"
    file_path.touch()
    uploader = _make_mocked_file_uploader(
        monkeypatch,
        file_path=file_path,
        remote_path="path/to/file/on/remote",
        data_connection_id="data-connection-id",
    )

    uploader.client.storage_service_upload_project_artifact.return_value = Mock(upload_id="test-upload-id")
    uploader.client.storage_service_upload_project_artifact_parts.return_value = V1UploadProjectArtifactPartsResponse(
        urls=[V1PresignedUrl(url="test-url-1", part_number=1)]
    )
    uploader.client.storage_service_complete_upload_project_artifact = Mock()

    uploader()

    uploader.client.storage_service_upload_project_artifact.assert_called_once_with(
        body=StorageServiceUploadProjectArtifactBody(
            filename="path/to/file/on/remote",
            cluster_id="test-cluster-id",
            data_connection_id="data-connection-id",
        ),
        project_id="test-project-id",
    )
    uploader.client.storage_service_upload_project_artifact_parts.assert_called_once_with(
        StorageServiceUploadProjectArtifactPartsBody(
            filename="path/to/file/on/remote",
            parts=[1],
            cluster_id="test-cluster-id",
            data_connection_id="data-connection-id",
        ),
        "test-project-id",
        "test-upload-id",
    )
    uploader.client.storage_service_complete_upload_project_artifact.assert_called_once_with(
        body=StorageServiceCompleteUploadProjectArtifactBody(
            filename="path/to/file/on/remote",
            parts=[mock.ANY],
            upload_id="test-upload-id",
            cluster_id="test-cluster-id",
            data_connection_id="data-connection-id",
        ),
        project_id="test-project-id",
    )


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
    assert len(resolve_path_mappings({}, None, None)) == 0

    assert len(resolve_path_mappings({}, "", "")) == 0

    path_mappings = resolve_path_mappings({}, "/output", "efs:some-connection:some-path")
    assert len(path_mappings) == 1
    assert isinstance(path_mappings[0], V1PathMapping)
    assert path_mappings[0].container_path == "/output"
    assert path_mappings[0].connection_name == "some-connection"
    assert path_mappings[0].connection_path == "some-path"

    with pytest.raises(
        RuntimeError,
        match=re.escape("Artifacts remote need to be of format efs:connection_name[:path] but got some-connection"),
    ):
        resolve_path_mappings({}, "/output", "some-connection")

    with pytest.raises(
        RuntimeError, match="If Artifacts remote is specified, artifacts local should be specified as well"
    ):
        resolve_path_mappings({}, "", "efs:some-connection:some-path")

    path_mappings = resolve_path_mappings(
        {
            "/path1": "conn1:remotepath1",
            "/path2": "conn2",
        },
        "/output",
        "efs:some-connection:some-path",
    )

    assert len(path_mappings) == 3
    assert all(isinstance(x, V1PathMapping) for x in path_mappings)

    assert path_mappings[0].container_path == "/path1"
    assert path_mappings[0].connection_name == "conn1"
    assert path_mappings[0].connection_path == "remotepath1"

    assert path_mappings[1].container_path == "/path2"
    assert path_mappings[1].connection_name == "conn2"
    assert path_mappings[1].connection_path == ""

    assert path_mappings[2].container_path == "/output"
    assert path_mappings[2].connection_name == "some-connection"
    assert path_mappings[2].connection_path == "some-path"


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


def _make_single_part_uploader(tmp_path, progress_bar=False, notify_completion=False, headers=None):
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("hello world")
    return utils._SinglePartFileUploader(
        client=Mock(),
        file_path=str(file_path),
        url="http://example.com/upload",
        query_params={"token": "test-token"},
        progress_bar=progress_bar,
        headers=headers,
        notify_completion=notify_completion,
    )


@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_basic(mock_requests, tmp_path):
    uploader = _make_single_part_uploader(tmp_path)

    mock_requests.put.return_value = Mock(status_code=200)

    uploader()

    assert mock_requests.put.call_count == 1
    call = mock_requests.put.call_args
    assert call.args[0] == "http://example.com/upload"
    assert call.kwargs["params"] == {"token": "test-token"}
    assert call.kwargs["timeout"] == 30
    assert call.kwargs["headers"] is None


@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_with_progress_bar(mock_requests, tmp_path):
    uploader = _make_single_part_uploader(tmp_path, progress_bar=True)

    mock_requests.put.return_value = Mock(status_code=200)

    uploader()

    assert mock_requests.put.call_count == 1
    call = mock_requests.put.call_args
    # Body should be wrapped in _IterableFileWrapper when progress_bar=True
    assert isinstance(call.kwargs["data"], utils._IterableFileWrapper)


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_retries_on_http_error(mock_requests, _, tmp_path):
    uploader = _make_single_part_uploader(tmp_path)

    mock_requests.put.side_effect = [
        requests.exceptions.RequestException(),
        Mock(status_code=200),
    ]

    uploader()

    assert mock_requests.put.call_count == 2


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_retries_on_transient_status(mock_requests, _, tmp_path):
    uploader = _make_single_part_uploader(tmp_path)

    # A transient 503 must be retried rather than failing immediately.
    mock_requests.put.side_effect = [
        Mock(status_code=503),
        Mock(status_code=200),
    ]

    uploader()

    assert mock_requests.put.call_count == 2


@mock.patch("time.sleep", return_value=None)
@mock.patch("lightning_sdk.api.utils.requests")
def test_single_part_uploader_does_not_retry_client_error(mock_requests, _, tmp_path):
    uploader = _make_single_part_uploader(tmp_path)

    # A non-transient 4xx should fail immediately without retrying.
    mock_requests.put.return_value = Mock(status_code=403)

    with pytest.raises(RuntimeError, match="Failed to upload file"):
        uploader()

    assert mock_requests.put.call_count == 1
