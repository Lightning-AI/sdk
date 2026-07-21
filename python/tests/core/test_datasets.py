import zipfile
from unittest import mock

import pytest

from lightning_sdk.datasets import UploadedDatasetInfo, upload_dataset


@pytest.fixture()
def upload_dependencies():
    teamspace = mock.MagicMock()
    teamspace.id = "project-1"
    teamspace.name = "my-teamspace"

    with (
        mock.patch("lightning_sdk.datasets._get_teamspace", return_value=teamspace),
        mock.patch("lightning_sdk.datasets.raise_access_error_if_not_allowed"),
        mock.patch("lightning_sdk.datasets._upload_dataset", return_value={"version": "v1"}) as upload,
    ):
        yield upload


def test_upload_dataset_as_zip(upload_dependencies, tmp_path):
    root_file = tmp_path / "root.txt"
    root_file.write_text("root contents", encoding="utf-8")
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    nested_file = nested_directory / "child.txt"
    nested_file.write_text("nested contents", encoding="utf-8")

    captured = {}

    def inspect_archive(**kwargs):
        archive_path = kwargs["file_paths"][0]
        captured["archive_path"] = archive_path
        captured["kwargs"] = kwargs
        assert archive_path.exists()
        with zipfile.ZipFile(archive_path) as archive:
            assert sorted(archive.namelist()) == ["nested/child.txt", "root.txt"]
            assert archive.read("root.txt") == b"root contents"
            assert archive.read("nested/child.txt") == b"nested contents"
            assert all(member.compress_type == zipfile.ZIP_DEFLATED for member in archive.infolist())
        return {"version": "v1"}

    upload_dependencies.side_effect = inspect_archive

    result = upload_dataset(
        "my-org/my-teamspace/my-dataset",
        tmp_path,
        cloud_account="cloud-1",
        progress_bar=False,
        num_workers=7,
        as_zip=True,
    )

    kwargs = captured["kwargs"]
    assert len(kwargs["file_paths"]) == 1
    assert kwargs["file_paths"][0].name == "my-dataset.zip"
    assert kwargs["relative_paths"] == ["my-dataset.zip"]
    assert kwargs["cluster_id"] == "cloud-1"
    assert kwargs["progress_bar"] is False
    assert kwargs["num_workers"] == 7
    assert not captured["archive_path"].exists()
    assert not (tmp_path / "my-dataset.zip").exists()
    assert result == UploadedDatasetInfo(name="my-dataset", version="v1", teamspace="my-teamspace")


def test_upload_dataset_as_zip_cleans_up_after_failure(upload_dependencies, tmp_path):
    source_file = tmp_path / "source.txt"
    source_file.write_text("contents", encoding="utf-8")
    captured = {}

    def fail_upload(**kwargs):
        captured["archive_path"] = kwargs["file_paths"][0]
        assert captured["archive_path"].exists()
        raise RuntimeError("upload failed")

    upload_dependencies.side_effect = fail_upload

    with pytest.raises(RuntimeError, match="upload failed"):
        upload_dataset(
            "my-org/my-teamspace/my-dataset",
            source_file,
            cloud_account="cloud-1",
            as_zip=True,
        )

    assert not captured["archive_path"].exists()
    assert source_file.exists()


def test_upload_dataset_default_uploads_files_individually(upload_dependencies, tmp_path):
    source_file = tmp_path / "source.txt"
    source_file.write_text("contents", encoding="utf-8")

    with mock.patch("lightning_sdk.datasets.tempfile.TemporaryDirectory") as temporary_directory:
        result = upload_dataset(
            "my-org/my-teamspace/my-dataset",
            source_file,
            cloud_account="cloud-1",
            num_workers=5,
        )

    temporary_directory.assert_not_called()
    upload_dependencies.assert_called_once_with(
        project_id="project-1",
        name="my-dataset",
        version=None,
        cluster_id="cloud-1",
        file_paths=[source_file],
        relative_paths=["source.txt"],
        progress_bar=True,
        num_workers=5,
    )
    assert result == UploadedDatasetInfo(name="my-dataset", version="v1", teamspace="my-teamspace")
