import pytest

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.legacy.upload import _file
from tests.cli.help import assert_help_contains


def test_file_upload_help() -> None:
    assert_help_contains("lightning file upload --help", "Usage: lightning file upload", "Upload a file to a Studio.")


def test_files_upload_help() -> None:
    assert_help_contains("lightning files upload --help", "Usage: lightning files upload", "Upload a file to a Studio.")


def test_upload_file_legacy_help() -> None:
    assert_help_contains(
        "lightning upload file --help",
        "Deprecation warning:",
        "Use `lightning file upload` instead of `lightning upload file`.",
        "Usage: lightning upload file [OPTIONS] PATH",
    )


def test_upload_file_validation_not_exists(tmp_path) -> None:
    path = tmp_path / "file.txt"

    with pytest.raises(FileNotFoundError):
        _file(path)


def test_upload_file_validation_is_a_folder(tmp_path) -> None:
    path = tmp_path / "files"
    path.mkdir()

    with pytest.raises(StudioCliError):
        _file(path)
