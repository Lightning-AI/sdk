import pytest
from unittest import mock
from unittest.mock import Mock, AsyncMock, mock_open, MagicMock, ANY, PropertyMock
import lightning_sdk.api.utils
from lightning_sdk.machine import Machine
from lightning_sdk.api.utils import _machine_to_compute_name, _download_model_files, _ModelFileUploader, _FileUploader, _FileDownloader
from lightning_sdk.lightning_cloud.openapi import (
    ProjectIdStorageBody,
    V1SignedUrl,
    V1PresignedUrl,
    UploadIdPartsBody,
    V1UploadProjectArtifactPartsResponse,
    UploadsUploadIdBody,
    VersionUploadsBody,
)


def _make_mocked_file_uploader(monkeypatch, file_path, remote_path):
    # Threadpools don't like mocks as input, so we just use a regular map here
    monkeypatch.setattr(lightning_sdk.api.utils.ThreadPoolExecutor, "map", map)
    uploader = _FileUploader(
        client=Mock(),
        teamspace_id="test-project-id",
        cluster_id="test-cluster-id",
        progress_bar=False,
        file_path=file_path,
        remote_path=remote_path,
    )
    return uploader


def test_file_uploader_path_exists(monkeypatch):
    with pytest.raises(FileNotFoundError):
        _make_mocked_file_uploader(monkeypatch, file_path="not-exist", remote_path="any")


@pytest.mark.parametrize(
    "machine,compute_name",
    [
        (Machine.CPU, "cpu-4"),
        (Machine.L40S_X_8, "g6e.48xlarge"),
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
        body=ProjectIdStorageBody(filename="path/to/file/on/remote", cluster_id="test-cluster-id"),
        project_id="test-project-id",
    )
    uploader.client.storage_service_upload_project_artifact_parts.assert_called_once_with(
        UploadsUploadIdBody(filename="path/to/file/on/remote", parts=[1], cluster_id="test-cluster-id"),
        "test-project-id",
        "test-upload-id",
    )
    uploader.client.storage_service_complete_upload_project_artifact.assert_called_once()

    # 0 because mocked data has length 0
    uploader.progress_bar.update.call_args_list == [mock.call(0), mock.call(0)]


def _make_mocked_model_uploader(monkeypatch, file_path, remote_path):
    # Threadpools don't like mocks as input, so we just use a regular map here
    monkeypatch.setattr(lightning_sdk.api.utils.ThreadPoolExecutor, "map", map)
    uploader = _ModelFileUploader(
        client=Mock(),
        model_id="test-model-id",
        version="test-version",
        teamspace_id="test-project-id",
        cluster_id="test-cluster-id",
        progress_bar=False,
        file_path=file_path,
        remote_path=remote_path,
    )
    uploader.api = Mock()
    return uploader


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
    uploader.api.models_store_create_multi_part_upload.return_value = Mock(upload_id="test-upload-id")
    uploader.api.models_store_get_model_file_upload_urls.return_value = Mock(
        urls=[
            V1SignedUrl(url="test-url-1", part_number=1),
            V1SignedUrl(url="test-url-2", part_number=2),
        ]
    )
    uploader.api.models_store_complete_multi_part_upload = Mock()

    uploader()

    uploader.api.models_store_create_multi_part_upload.assert_called_once_with(
        VersionUploadsBody(filepath="path/to/file/on/remote"),
        model_id="test-model-id",
        project_id="test-project-id",
        version="test-version",
    )
    uploader.api.models_store_get_model_file_upload_urls.assert_called_once_with(
        UploadIdPartsBody(filepath="path/to/file/on/remote", parts=[1]),
        model_id="test-model-id",
        project_id="test-project-id",
        version="test-version",
        upload_id="test-upload-id",
    )
    uploader.api.models_store_complete_multi_part_upload.assert_called_once()

    # 0 because mocked data has length 0
    uploader.progress_bar.update.call_args_list == [mock.call(0), mock.call(0)]


@mock.patch("lightning_sdk.api.utils.ModelsStoreApi")
@mock.patch("lightning_sdk.api.utils._FileDownloader.download")
def test_download_model_files(download_mock, api_mock, tmp_path):
    api_mock.return_value.models_store_get_model_files.return_value = Mock(
        model_id="test-model-id",
        project_id="test-project-id",
        version="latest",
        filepaths=["path/to/file1", "path/to/file2"],
    )

    api_mock.return_value.models_store_get_model_file_url.side_effect = [
        Mock(url="http://example.com/file1", size=10),
        Mock(url="http://example.com/file2", size=10),
    ]

    delay = 0.01

    _download_model_files(
        client=Mock(), teamspace_id="test-project-id", name="modelname", version="latest", download_dir=tmp_path, progress_bar=False
    )

    api_mock.return_value.models_store_get_model_files.assert_called_once_with(project_id="test-project-id", name="modelname", version="latest")

    assert api_mock.return_value.models_store_get_model_file_url.call_count == 2
    api_mock.return_value.models_store_get_model_file_url.assert_any_call(
        project_id="test-project-id", model_id="test-model-id", version="latest", filepath="path/to/file1"
    )
    api_mock.return_value.models_store_get_model_file_url.assert_any_call(
        project_id="test-project-id", model_id="test-model-id", version="latest", filepath="path/to/file2"
    )

    assert download_mock.call_count == 2


def mock_iter_content(chunk_size):
    chunks = [b"test_data"]
    for chunk in chunks:
        yield chunk


@mock.patch('requests.get')
def test_download_chunk_success(mock_get):
    url = "http://example.com"
    start = 0
    end = 100
    filename = "test_file"

    mock_response = Mock()
    mock_response.status_code = 206
    mock_response.iter_content = mock_iter_content

    mock_get.return_value.__enter__.return_value = mock_response

    mock_client = MagicMock()
    mock_client.api_client.call_api.return_value.url = url

    file_downloader = _FileDownloader(
        client=mock_client,
        model_id="foo",
        version="1",
        teamspace_id="bar",
        remote_path="some",
        file_path=filename,
    )

    with mock.patch("builtins.open", mock_open()) as mock_file:
        file_downloader._download_chunk(filename, (start, end))

        mock_get.assert_called_once_with(url, headers={"Range": "bytes=0-100"}, stream=True)

        mock_file.assert_called_once_with(filename, "r+b")
        mock_file().seek.assert_called_once_with(start)
        mock_file().write.assert_called_once_with(b"test_data")


@mock.patch('requests.get')
@mock.patch.object(lightning_sdk.api.utils._FileDownloader, "url", new_callable=PropertyMock)
@mock.patch("lightning_sdk.api.utils._FileDownloader.refresh")
def test_download_chunk_failure(mock_refresh, mock_url, mock_get):
    url = "http://example.com"
    start = 0
    end = 100
    filename = "test_file"

    mock_response = Mock()
    mock_response.status_code = 403

    mock_get.return_value.__enter__.return_value = mock_response

    mock_client = MagicMock()
    mock_client.api_client.call_api.return_value.url = url

    mock_url.return_value = url

    file_downloader = _FileDownloader(
        client=mock_client,
        model_id="foo",
        version="1",
        teamspace_id="bar",
        remote_path="some",
        file_path=filename,
    )

    file_downloader._download_chunk(filename, (start, end))

    mock_get.assert_called_once_with(url, headers={"Range": "bytes=0-100"}, stream=True)
    assert mock_response.raise_for_status.call_count == 1

    assert mock_refresh.call_count == 2
