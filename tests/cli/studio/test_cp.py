import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.studio.cp import cp_download, cp_impl, cp_studio_file, cp_upload, resolve_studio


def test_cp_help():
    result = subprocess.run("lightning studio cp --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning studio cp [OPTIONS] SOURCE DESTINATION

  Copy a Studio file.

  SOURCE: Source file to copy from. For Studio files, use the format
  lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

  DESTINATION: Destination file to copy to. For Studio files, use the format
  lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>.

  Example:     lightning studio cp source.txt lit://<owner>/<my-
  teamspace>/studios/<my-studio>/destination.txt

Options:
  --help  Show this message and exit.
"""
    )


def test_cp_impl_both_studio_files_raises_error():
    """Test that providing both source and destination as Studio files raises an error."""
    with pytest.raises(ValueError, match="Both source and destination cannot be Studio files"):
        cp_impl(
            source="lit://owner/teamspace/studios/studio1/file1.txt",
            destination="lit://owner/teamspace/studios/studio2/file2.txt",
        )


def test_cp_impl_both_local_files_raises_error():
    """Test that providing both source and destination as local files raises an error."""
    with pytest.raises(ValueError, match="Either source or destination must be a Studio file"):
        cp_impl(source="local_file1.txt", destination="local_file2.txt")


def test_cp_upload_with_nonexistent_raises_error(tmp_path: Path):
    """Test that providing a nonexistent file and folder path raises FileNotFoundError."""
    nonexistent_file = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError, match="The provided path does not exist"):
        cp_upload(
            local_file_path=str(nonexistent_file),
            studio_file_path="lit://owner/teamspace/studios/test-studio/dest.txt",
        )
    nonexistent_dir = tmp_path / "nonexistent_dir"

    with pytest.raises(FileNotFoundError, match="The provided path does not exist"):
        cp_upload(
            local_file_path=str(nonexistent_dir),
            studio_file_path="lit://owner/teamspace/studios/test-studio/dest/",
        )


def test_cp_download_with_nonexistent_file_raises_error(tmp_path: Path):
    """Test that providing a nonexistent studio file path raises FileNotFoundError."""
    test_file = tmp_path / "test_file.txt"

    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "/nonexistent.txt",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": False}

    with (
        patch("lightning_sdk.cli.studio.cp.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.cp.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.cp.Console"),  # silence console output
        pytest.raises(FileNotFoundError, match="The provided path does not exist in the studio"),
    ):
        cp_download(
            studio_path="lit://test-owner/test-teamspace/studios/test-studio/nonexistent.txt",
            local_path=str(test_file),
        )


def test_cp_upload_successful(tmp_path: Path):
    """Test successful file upload to Studio."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt",
        )

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")

    test_dir = tmp_path
    test_dir_file = test_dir / "test_file.txt"
    test_dir_file.write_text("test content")

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_upload(
            local_file_path=str(test_dir),
            studio_file_path="lit://test-owner/test-teamspace/studios/test-studio/remote-dir/",
        )

        mock_studio_instance.upload_folder.assert_called_once_with(str(test_dir), "remote-dir/")


def test_cp_download_successful(tmp_path: Path):
    """Test successful file download from Studio."""
    test_file = tmp_path / "test_file.txt"

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.download_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_download(
            studio_path="lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt",
            local_path=str(test_file),
        )

        mock_studio_instance.download_file.assert_called_once_with("remote_file.txt", str(test_file))


def test_cp_upload_without_teamspace(tmp_path: Path):
    """Test that cp_upload works when teamspace is not provided in the path."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "default-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "default-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-studio/remote_file.txt",
        )

        mock_teamspace_menu.assert_called_once_with(teamspace=None)
        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


def test_cp_download_without_teamspace(tmp_path: Path):
    """Test that cp_download works when teamspace is not provided in the path."""
    test_file = tmp_path / "test_file.txt"

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "default-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "default-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.download_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_download(
            studio_path="lit://test-studio/remote_file.txt",
            local_path=str(test_file),
        )

        mock_teamspace_menu.assert_called_once_with(teamspace=None)
        mock_studio_instance.download_file.assert_called_once_with("remote_file.txt", str(test_file))


def test_cp_studio_file_upload_integration(tmp_path: Path):
    """Test the full cp_studio_file command for upload."""
    runner = CliRunner()
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        result = runner.invoke(
            cp_studio_file, [str(test_file), "lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt"]
        )

        assert result.exit_code == 0
        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


def test_cp_studio_file_download_integration(tmp_path: Path):
    """Test the full cp_studio_file command for download."""
    runner = CliRunner()
    test_file = tmp_path / "test_file.txt"

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.download_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        result = runner.invoke(
            cp_studio_file, ["lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt", str(test_file)]
        )

        assert result.exit_code == 0
        mock_studio_instance.download_file.assert_called_once_with("remote_file.txt", str(test_file))


def test_resolve_studio_with_teamspace():
    """Test that resolve_studio correctly resolves studio with provided owner and teamspace."""
    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        result = resolve_studio(studio_name="test-studio", teamspace="test-teamspace", owner="test-owner")

        assert result == mock_studio_instance
        mock_owner_menu.assert_called_once_with(owner="test-owner")
        mock_teamspace_menu.assert_called_once_with(teamspace="test-teamspace")
        mock_studio_menu.assert_called_once_with(studio="test-studio")


def test_resolve_studio_without_teamspace():
    """Test that resolve_studio works when teamspace and owner are None."""
    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "default-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "default-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        result = resolve_studio(studio_name="test-studio", teamspace=None, owner=None)

        assert result == mock_studio_instance
        mock_owner_menu.assert_called_once_with(owner=None)
        mock_teamspace_menu.assert_called_once_with(teamspace=None)
        mock_studio_menu.assert_called_once_with(studio="test-studio")


def test_cp_upload_with_nested_path(tmp_path: Path):
    """Test uploading a file with nested destination path."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-studio/folder/subfolder/remote_file.txt",
        )

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "folder/subfolder/remote_file.txt")


def test_cp_download_with_nested_path(tmp_path: Path):
    """Test downloading a file with nested destination path."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_download(
            studio_path="lit://test-studio/folder/subfolder/remote_file.txt",
            local_path=str(test_file),
        )

        mock_studio_instance.download_file.assert_called_once_with("folder/subfolder/remote_file.txt", str(test_file))


def test_cp_impl_dispatches_to_upload(tmp_path: Path):
    """Test that cp_impl correctly dispatches to upload when destination has lit://."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_impl(source=str(test_file), destination="lit://test-studio/remote_file.txt")

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


def test_cp_impl_dispatches_to_download(tmp_path: Path):
    """Test that cp_impl correctly dispatches to download when source has lit://."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.download_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_impl(source="lit://test-studio/remote_file.txt", destination=str(test_file))

        mock_studio_instance.download_file.assert_called_once_with("remote_file.txt", str(test_file))
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.download_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_impl(source="lit://test-studio/remote_file.txt", destination=str(test_file))

        mock_studio_instance.download_file.assert_called_once_with("remote_file.txt", str(test_file))


def test_cp_upload_prints_correct_messages(tmp_path: Path):
    """Test that cp_upload prints the correct console messages."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    mock_console = MagicMock()

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
        patch("lightning_sdk.cli.studio.cp.Console", return_value=mock_console),
    ):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-studio/remote_file.txt",
        )

        assert mock_console.print.call_count == 2
        first_call_arg = str(mock_console.print.call_args_list[0][0][0])
        assert "Uploading to test-teamspace/test-studio" in first_call_arg

        second_call_arg = str(mock_console.print.call_args_list[1][0][0])
        assert "See your file at" in second_call_arg
        assert "test-owner" in second_call_arg
        assert "test-teamspace" in second_call_arg
        assert "test-studio" in second_call_arg


def test_cp_download_prints_correct_messages(tmp_path: Path):
    """Test that cp_download prints the correct console messages."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    mock_console = MagicMock()

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
        patch("lightning_sdk.cli.studio.cp.Console", return_value=mock_console),
    ):
        cp_download(
            studio_path="lit://test-studio/remote_file.txt",
            local_path=str(test_file),
        )

        assert mock_console.print.call_count == 2
        first_call_arg = str(mock_console.print.call_args_list[0][0][0])
        assert "Downloading from test-teamspace/test-studio" in first_call_arg

        second_call_arg = str(mock_console.print.call_args_list[1][0][0])

        assert "test_file.txt" in second_call_arg


def test_cp_studio_file_with_special_characters_in_filename(tmp_path: Path):
    """Test uploading a file with special characters in the filename."""
    test_file = tmp_path / "test file with spaces.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "test-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "test-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "test-studio"
    mock_studio_instance.teamspace.name = "test-teamspace"
    mock_studio_instance.owner.name = "test-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
    ):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-studio/file.txt",
        )

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "file.txt")


def test_cp_upload_url_construction(tmp_path: Path):
    """Test that the Studio URL is constructed correctly with port removal."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")

    mock_owner_menu = MagicMock()
    mock_owner_menu.return_value = "my-owner"

    mock_teamspace_menu = MagicMock()
    mock_teamspace_menu.return_value = "my-teamspace"

    mock_studio_menu = MagicMock()
    mock_studio_instance = MagicMock()
    mock_studio_instance.name = "my-studio"
    mock_studio_instance.teamspace.name = "my-teamspace"
    mock_studio_instance.owner.name = "my-owner"
    mock_studio_instance.upload_file = MagicMock()
    mock_studio_menu.return_value = mock_studio_instance

    mock_console = MagicMock()

    with (
        patch("lightning_sdk.cli.utils.studio_filesystem.OwnerMenu", return_value=mock_owner_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.TeamspacesMenu", return_value=mock_teamspace_menu),
        patch("lightning_sdk.cli.utils.studio_filesystem.StudiosMenu", return_value=mock_studio_menu),
        patch("lightning_sdk.cli.studio.cp.Console", return_value=mock_console),
    ):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://my-studio/remote_file.txt",
        )

        second_call_arg = str(mock_console.print.call_args_list[1][0][0])
        assert ":443" not in second_call_arg
        assert "https://lightning.ai/my-owner/my-teamspace/studios/my-studio" in second_call_arg
