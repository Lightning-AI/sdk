import pytest

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.legacy.upload import _folder
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_folder_upload_help() -> None:
    assert_help_contains(
        "lightning folder upload --help", "Usage: lightning folder upload", "Upload a folder to a Studio."
    )


@mock_command_logging
def test_folders_upload_help() -> None:
    assert_help_contains(
        "lightning folders upload --help", "Usage: lightning folders upload", "Upload a folder to a Studio."
    )


@mock_command_logging
def test_upload_folder_legacy_help() -> None:
    assert_help_contains(
        "lightning upload folder --help",
        "Deprecation warning:",
        "Use `lightning cp -r` instead of `lightning upload folder`.",
        "Usage: lightning upload folder [OPTIONS] SOURCE [DESTINATION]",
    )


@mock_command_logging
def test_upload_folder_validation_is_a_file(tmp_path) -> None:
    path = tmp_path / "hello.txt"
    path.write_text("test", encoding="utf-8")

    with pytest.raises(StudioCliError):
        _folder(path)


@mock_command_logging
def test_upload_folder_validation_not_exists(tmp_path) -> None:
    path = tmp_path / "files"

    with pytest.raises(FileNotFoundError):
        _folder(path)
