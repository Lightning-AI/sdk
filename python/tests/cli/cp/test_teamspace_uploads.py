import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.cli.cp.teamspace_uploads import cp_upload


def test_cp_upload_with_nonexistent_path_raises_error(tmp_path: Path):
    """Test that providing a nonexistent file path raises FileNotFoundError."""
    nonexistent_file = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError, match="The provided path does not exist"):
        cp_upload(
            local_file_path=str(nonexistent_file),
            teamspace_path="lit://owner/teamspace/uploads/dest.txt",
            options={},
        )

    nonexistent_dir = tmp_path / "nonexistent_dir"

    with pytest.raises(FileNotFoundError, match="The provided path does not exist"):
        cp_upload(
            local_file_path=str(nonexistent_dir),
            teamspace_path="lit://owner/teamspace/uploads/dest/",
            options={"recursive": True},
        )


def test_cp_upload_file_successful(tmp_path: Path):
    """Test successful file upload to teamspace."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_parse_result = {
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "remote_file.txt",
    }

    mock_teamspace = MagicMock()
    mock_teamspace.name = "test-teamspace"
    mock_teamspace.owner.name = "test-owner"
    mock_teamspace.upload_file = MagicMock()

    with (
        patch("lightning_sdk.cli.cp.teamspace_uploads.parse_teamspace_uploads_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.cp.teamspace_uploads.resolve_teamspace", return_value=mock_teamspace),
        patch("lightning_sdk.cli.cp.teamspace_uploads.Console"),
    ):
        cp_upload(
            local_file_path=str(test_file),
            teamspace_path="lit://test-owner/test-teamspace/uploads/remote_file.txt",
            options={},
        )

        mock_teamspace.upload_file.assert_called_once_with(
            str(test_file), "Uploads/remote_file.txt", cloud_account=None
        )


def test_cp_upload_file_with_cloud_account(tmp_path: Path):
    """Test file upload with cloud_account option."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_parse_result = {
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "remote_file.txt",
    }

    mock_teamspace = MagicMock()
    mock_teamspace.name = "test-teamspace"
    mock_teamspace.owner.name = "test-owner"
    mock_teamspace.upload_file = MagicMock()

    with (
        patch("lightning_sdk.cli.cp.teamspace_uploads.parse_teamspace_uploads_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.cp.teamspace_uploads.resolve_teamspace", return_value=mock_teamspace),
        patch("lightning_sdk.cli.cp.teamspace_uploads.Console"),
    ):
        cp_upload(
            local_file_path=str(test_file),
            teamspace_path="lit://test-owner/test-teamspace/uploads/remote_file.txt",
            options={"cloud_account": "my-cloud-account"},
        )

        mock_teamspace.upload_file.assert_called_once_with(
            str(test_file), "Uploads/remote_file.txt", cloud_account="my-cloud-account"
        )


def test_cp_upload_folder_successful(tmp_path: Path):
    """Test successful folder upload to teamspace."""
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()
    test_file = test_dir / "test_file.txt"
    test_file.write_text("test content")

    mock_parse_result = {
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "remote_folder/",
    }

    mock_teamspace = MagicMock()
    mock_teamspace.name = "test-teamspace"
    mock_teamspace.owner.name = "test-owner"
    mock_teamspace.upload_folder = MagicMock()

    with (
        patch("lightning_sdk.cli.cp.teamspace_uploads.parse_teamspace_uploads_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.cp.teamspace_uploads.resolve_teamspace", return_value=mock_teamspace),
        patch("lightning_sdk.cli.cp.teamspace_uploads.Console"),
    ):
        cp_upload(
            local_file_path=str(test_dir),
            teamspace_path="lit://test-owner/test-teamspace/uploads/remote_folder/",
            options={"recursive": True},
        )

        mock_teamspace.upload_folder.assert_called_once_with(
            str(test_dir), "Uploads/remote_folder/", cloud_account=None
        )


def test_cp_upload_folder_without_recursive_raises_error(tmp_path: Path):
    """Test that uploading a folder without -r flag raises an error."""
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()
    test_file = test_dir / "test_file.txt"
    test_file.write_text("test content")

    mock_parse_result = {
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "remote_folder/",
    }

    mock_teamspace = MagicMock()
    mock_teamspace.name = "test-teamspace"
    mock_teamspace.owner.name = "test-owner"

    with (
        patch("lightning_sdk.cli.cp.teamspace_uploads.parse_teamspace_uploads_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.cp.teamspace_uploads.resolve_teamspace", return_value=mock_teamspace),
        patch("lightning_sdk.cli.cp.teamspace_uploads.Console"),
        pytest.raises(ValueError, match="is a directory. Use -r flag to copy directories recursively"),
    ):
        cp_upload(
            local_file_path=str(test_dir),
            teamspace_path="lit://test-owner/test-teamspace/uploads/remote_folder/",
            options={"recursive": False},
        )


def test_cp_upload_file_to_directory_path(tmp_path: Path):
    """Test uploading a file when destination ends with / (directory)."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_parse_result = {
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "remote_folder",
    }

    mock_teamspace = MagicMock()
    mock_teamspace.name = "test-teamspace"
    mock_teamspace.owner.name = "test-owner"
    mock_teamspace.upload_file = MagicMock()

    with (
        patch("lightning_sdk.cli.cp.teamspace_uploads.parse_teamspace_uploads_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.cp.teamspace_uploads.resolve_teamspace", return_value=mock_teamspace),
        patch("lightning_sdk.cli.cp.teamspace_uploads.Console"),
    ):
        cp_upload(
            local_file_path=str(test_file),
            teamspace_path="lit://test-owner/test-teamspace/uploads/remote_folder/",
            options={},
        )

        expected_path = os.path.join("Uploads", os.path.join("remote_folder", "test_file.txt"))
        mock_teamspace.upload_file.assert_called_once_with(str(test_file), expected_path, cloud_account=None)


def test_cp_upload_with_nested_path(tmp_path: Path):
    """Test uploading a file with nested destination path."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_parse_result = {
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "folder/subfolder/remote_file.txt",
    }

    mock_teamspace = MagicMock()
    mock_teamspace.name = "test-teamspace"
    mock_teamspace.owner.name = "test-owner"
    mock_teamspace.upload_file = MagicMock()

    with (
        patch("lightning_sdk.cli.cp.teamspace_uploads.parse_teamspace_uploads_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.cp.teamspace_uploads.resolve_teamspace", return_value=mock_teamspace),
        patch("lightning_sdk.cli.cp.teamspace_uploads.Console"),
    ):
        cp_upload(
            local_file_path=str(test_file),
            teamspace_path="lit://test-owner/test-teamspace/uploads/folder/subfolder/remote_file.txt",
            options={},
        )

        mock_teamspace.upload_file.assert_called_once_with(
            str(test_file), "Uploads/folder/subfolder/remote_file.txt", cloud_account=None
        )
