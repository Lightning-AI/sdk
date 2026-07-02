"""Tests for Studio rm command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.studio.rm import rm_file, rm_folder, rm_impl, rm_studio_file
from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_rm_help():
    """Test the rm command help text."""
    result_text = command_text("lightning studio rm --help")

    assert "Usage: lightning studio rm [OPTIONS] PATH" in result_text
    assert "Remove a Studio file or directory." in result_text
    assert "studios/<my-studio>/<filepath>" in result_text
    assert "--recursive  -r" in result_text
    assert "--force      -f" in result_text


@mock_command_logging
def test_studios_rm_help() -> None:
    assert_help_contains(
        "lightning studios rm --help", "Usage: lightning studios rm", "Remove a Studio file or directory."
    )


@mock_command_logging
def test_rm_impl_local_path_raises_error():
    """Test that providing a non-Studio path raises an error."""
    with pytest.raises(ValueError, match="Path must be a Studio path starting with 'lit://'."):
        rm_impl(path="local_file.txt")


@mock_command_logging
def test_rm_impl_with_nonexistent_file_raises_error():
    """Test that removing a nonexistent file raises FileNotFoundError."""
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
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
        pytest.raises(FileNotFoundError, match="The provided path does not exist in the studio"),
    ):
        rm_impl(
            path="lit://test-owner/test-teamspace/studios/test-studio/nonexistent.txt",
            recursive=False,
            force=False,
        )


@mock_command_logging
def test_rm_impl_with_nonexistent_file_and_force_succeeds():
    """Test that removing a nonexistent file with -f flag succeeds silently."""
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
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
    ):
        result = rm_impl(
            path="lit://test-owner/test-teamspace/studios/test-studio/nonexistent.txt",
            recursive=False,
            force=True,
        )
        # returns None without raising
        assert result is None


@mock_command_logging
def test_rm_file_successful():
    """Test successful file removal from Studio."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "file.txt",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "file"}
    mock_selected_studio._studio_api.remove_file = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
    ):
        rm_impl(
            path="lit://test-owner/test-teamspace/studios/test-studio/file.txt",
            recursive=False,
            force=False,
        )

        mock_selected_studio._studio_api.remove_file.assert_called_once_with("studio-id", "teamspace-id", "file.txt")


@mock_command_logging
def test_rm_folder_without_recursive_flag_raises_error():
    """Test that removing a folder without -r flag raises an error."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "/my-folder",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "directory"}

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
        pytest.raises(ValueError, match="is a directory. Use -r flag to remove directories recursively"),
    ):
        rm_impl(
            path="lit://test-owner/test-teamspace/studios/test-studio/my-folder",
            recursive=False,
            force=False,
        )


@mock_command_logging
def test_rm_folder_with_recursive_flag_succeeds():
    """Test that removing a folder with -r flag succeeds."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "/my-folder",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "directory"}
    mock_selected_studio._studio_api.remove_folder = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
    ):
        rm_impl(
            path="lit://test-owner/test-teamspace/studios/test-studio/my-folder",
            recursive=True,
            force=False,
        )

        mock_selected_studio._studio_api.remove_folder.assert_called_once_with(
            "studio-id", "teamspace-id", "/my-folder"
        )


@mock_command_logging
def test_rm_studio_file_integration():
    """Test the full rm_studio_file command."""
    runner = CliRunner()

    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "file.txt",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "file"}
    mock_selected_studio._studio_api.remove_file = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
    ):
        result = runner.invoke(rm_studio_file, ["lit://test-owner/test-teamspace/studios/test-studio/file.txt"])

        assert result.exit_code == 0
        mock_selected_studio._studio_api.remove_file.assert_called_once_with("studio-id", "teamspace-id", "file.txt")


@mock_command_logging
def test_rm_prints_correct_messages():
    """Test that rm prints the correct console messages."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "file.txt",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "file"}
    mock_selected_studio._studio_api.remove_file = MagicMock()

    mock_console = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console", return_value=mock_console),
    ):
        rm_impl(
            path="lit://test-studio/file.txt",
            recursive=False,
            force=False,
        )

        assert mock_console.print.call_count == 2
        first_call_arg = str(mock_console.print.call_args_list[0][0][0])
        assert "Removing from test-teamspace/test-studio" in first_call_arg

        second_call_arg = str(mock_console.print.call_args_list[1][0][0])
        assert "Removed file: file.txt" in second_call_arg


@mock_command_logging
def test_rm_folder_prints_correct_messages():
    """Test that rm folder prints the correct console messages."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "/my-folder",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "directory"}
    mock_selected_studio._studio_api.remove_folder = MagicMock()

    mock_console = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console", return_value=mock_console),
    ):
        rm_impl(
            path="lit://test-studio/my-folder",
            recursive=True,
            force=False,
        )

        assert mock_console.print.call_count == 2
        first_call_arg = str(mock_console.print.call_args_list[0][0][0])
        assert "Removing from test-teamspace/test-studio" in first_call_arg

        second_call_arg = str(mock_console.print.call_args_list[1][0][0])
        assert "Removed directory: /my-folder" in second_call_arg


@mock_command_logging
def test_rm_with_nested_path():
    """Test removing a file with nested path."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "folder/subfolder/file.txt",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": True, "type": "file"}
    mock_selected_studio._studio_api.remove_file = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
    ):
        rm_impl(
            path="lit://test-studio/folder/subfolder/file.txt",
            recursive=False,
            force=False,
        )

        mock_selected_studio._studio_api.remove_file.assert_called_once_with(
            "studio-id", "teamspace-id", "folder/subfolder/file.txt"
        )


@mock_command_logging
def test_rm_file_function_calls_api():
    """Test that rm_file function calls the API correctly."""
    mock_selected_studio = MagicMock()
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.remove_file = MagicMock()

    mock_console = MagicMock()

    rm_file(selected_studio=mock_selected_studio, path="test.txt", console=mock_console)

    mock_selected_studio._studio_api.remove_file.assert_called_once_with("studio-id", "teamspace-id", "test.txt")
    mock_console.print.assert_called_once()
    assert "Removed file: test.txt" in str(mock_console.print.call_args[0][0])


@mock_command_logging
def test_rm_folder_function_calls_api():
    """Test that rm_folder function calls the API correctly."""
    mock_selected_studio = MagicMock()
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"
    mock_selected_studio._studio_api.remove_folder = MagicMock()

    mock_console = MagicMock()

    rm_folder(selected_studio=mock_selected_studio, path="/my-folder", console=mock_console)

    mock_selected_studio._studio_api.remove_folder.assert_called_once_with("studio-id", "teamspace-id", "/my-folder")
    mock_console.print.assert_called_once()
    assert "Removed directory: /my-folder" in str(mock_console.print.call_args[0][0])


@mock_command_logging
def test_rm_with_force_and_recursive():
    """Test removing a nonexistent folder with both -r and -f flags."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "/nonexistent-folder",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": False}

    with (
        patch("lightning_sdk.cli.studio.rm.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.rm.resolve_studio", return_value=mock_selected_studio),
        patch("lightning_sdk.cli.studio.rm.Console"),
    ):
        result = rm_impl(
            path="lit://test-owner/test-teamspace/studios/test-studio/nonexistent-folder",
            recursive=True,
            force=True,
        )
        # returns None without raising
        assert result is None
