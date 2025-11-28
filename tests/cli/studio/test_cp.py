import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.cli.studio.cp import cp_impl, cp_studio_file, cp_upload, resolve_studio


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


def test_cp_upload_with_directory_raises_error(tmp_path: Path):
    """Test that providing a directory path raises StudioCliError."""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    with pytest.raises(StudioCliError, match="The provided path is a folder"):
        cp_upload(local_file_path=str(test_dir), studio_file_path="lit://owner/teamspace/studios/test-studio/dest.txt")


def test_cp_upload_with_nonexistent_file_raises_error(tmp_path: Path):
    """Test that providing a nonexistent file path raises FileNotFoundError."""
    nonexistent_file = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError, match="The provided path does not exist"):
        cp_upload(
            local_file_path=str(nonexistent_file),
            studio_file_path="lit://owner/teamspace/studios/test-studio/dest.txt",
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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console"
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt",
        )

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console"
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-studio/remote_file.txt",
        )

        mock_teamspace_menu.assert_called_once_with(teamspace=None)
        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console"
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
        result = runner.invoke(
            cp_studio_file, [str(test_file), "lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt"]
        )

        assert result.exit_code == 0
        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


def test_cp_studio_file_download_not_implemented(tmp_path: Path):
    """Test that download functionality raises NotImplementedError."""
    runner = CliRunner()
    dest_file = tmp_path / "dest_file.txt"

    result = runner.invoke(cp_studio_file, ["test-studio://source_file.txt", str(dest_file)])

    assert result.exit_code != 0
    assert "NotImplementedError" in result.output or result.exception is not None


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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu):
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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu):
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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console"
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://test-studio/folder/subfolder/remote_file.txt",
        )

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "folder/subfolder/remote_file.txt")


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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console"
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
        cp_impl(source=str(test_file), destination="lit://test-studio/remote_file.txt")

        mock_studio_instance.upload_file.assert_called_once_with(str(test_file), "remote_file.txt")


def test_cp_impl_dispatches_to_download():
    """Test that cp_impl correctly dispatches to download when source has lit://."""
    with pytest.raises(NotImplementedError, match="Download functionality is not implemented yet"):
        cp_impl(source="lit://test-studio/source_file.txt", destination="local_file.txt")


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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console", return_value=mock_console
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console"
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai"):
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

    with patch("lightning_sdk.cli.studio.cp.OwnerMenu", return_value=mock_owner_menu), patch(
        "lightning_sdk.cli.studio.cp.TeamspacesMenu", return_value=mock_teamspace_menu
    ), patch("lightning_sdk.cli.studio.cp.StudiosMenu", return_value=mock_studio_menu), patch(
        "lightning_sdk.cli.studio.cp.Console", return_value=mock_console
    ), patch("lightning_sdk.cli.studio.cp._get_cloud_url", return_value="https://lightning.ai:443"):
        cp_upload(
            local_file_path=str(test_file),
            studio_file_path="lit://my-studio/remote_file.txt",
        )

        second_call_arg = str(mock_console.print.call_args_list[1][0][0])
        assert ":443" not in second_call_arg
        assert "https://lightning.ai/my-owner/my-teamspace/studios/my-studio" in second_call_arg
