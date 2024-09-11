import pytest
from unittest import mock
from unittest.mock import Mock
import lightning_sdk.api.utils
from lightning_sdk.api.utils import _download_model_files, _ModelFileUploader, _FileUploader
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


@mock.patch("lightning_sdk.api.utils.requests")
def test_file_uploader(_, tmp_path, monkeypatch):
    """Tests the basic calls that uploader makes to model store API."""

    file_path = tmp_path / "file"
    file_path.touch()
    uploader = _make_mocked_file_uploader(monkeypatch, file_path=file_path, remote_path="path/to/file/on/remote")

    uploader.progress_bar = Mock()

    uploader.client.lightningapp_instance_service_upload_project_artifact.return_value = Mock(
        upload_id="test-upload-id"
    )
    uploader.client.lightningapp_instance_service_upload_project_artifact_parts.return_value = (
        V1UploadProjectArtifactPartsResponse(
            urls=[
                V1PresignedUrl(url="test-url-1", part_number=1),
                V1PresignedUrl(url="test-url-2", part_number=2),
            ]
        )
    )

    uploader.client.lightningapp_instance_service_complete_upload_project_artifact = Mock()

    uploader()

    uploader.client.lightningapp_instance_service_upload_project_artifact.assert_called_once_with(
        body=ProjectIdStorageBody(filename="path/to/file/on/remote", cluster_id="test-cluster-id"),
        project_id="test-project-id",
    )
    uploader.client.lightningapp_instance_service_upload_project_artifact_parts.assert_called_once_with(
        UploadsUploadIdBody(filename="path/to/file/on/remote", parts=[1], cluster_id="test-cluster-id"),
        "test-project-id",
        "test-upload-id",
    )
    uploader.client.lightningapp_instance_service_complete_upload_project_artifact.assert_called_once()

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


@mock.patch("lightning_sdk.api.utils.requests")
@mock.patch("lightning_sdk.api.utils.ModelsStoreApi")
def test_download_model_files(api_mock, requests_mock, tmp_path):
    api_mock().models_store_get_model_files.return_value = Mock(
        model_id="test-model-id",
        project_id="test-project-id",
        version="latest",
        filepaths=["path/to/file1", "path/to/file2"],
    )
    requests_mock.get.return_value = Mock(iter_content=Mock(return_value=[b"chunk1", b"chunk2"]))

    _download_model_files(
        client=Mock(),
        name="user/modelname",
        version="latest",
        download_dir=tmp_path,
        progress_bar=False,
    )

    assert api_mock().models_store_get_model_file_url.call_count == 2
    api_mock().models_store_get_model_file_url.assert_called_with(
        filepath="path/to/file2",
        model_id="test-model-id",
        project_id="test-project-id",
        version="latest",
    )

    assert (tmp_path / "path/to/file1").exists()
    assert (tmp_path / "path/to/file2").exists()
