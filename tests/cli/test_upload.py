import pytest

from lightning_sdk.cli.upload import _Uploads
from lightning_sdk.cli.exceptions import StudioCliError

def test_upload_folder_validation_is_a_file(tmp_path):
    uploads = _Uploads()

    path = tmp_path / "hello.txt"
    path.write_text("test", encoding="utf-8")

    with pytest.raises(StudioCliError):
        uploads.folder(path)

def test_upload_folder_validation_not_exists(tmp_path):
    uploads = _Uploads()

    path = tmp_path / "files"

    with pytest.raises(FileNotFoundError):
        uploads.folder(path)

def test_upload_file_validation_not_exists(tmp_path):
    uploads = _Uploads()

    path = tmp_path / "file.txt"

    with pytest.raises(FileNotFoundError):
        uploads.file(path)

def test_upload_file_validation_is_a_folder(tmp_path):
    uploads = _Uploads()

    path = tmp_path / "files"
    path.mkdir()

    with pytest.raises(StudioCliError):
        uploads.file(path)
