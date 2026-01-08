import subprocess
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.studio.ls import ls_impl, ls_studio


def test_ls_help():
    """Test that the help message is displayed correctly."""
    result = subprocess.run("lightning studio ls --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert "Usage: lightning studio ls [OPTIONS] PATH" in result_text
    assert "List contents of a directory in Studio." in result_text
    assert "lit://<owner>/<teamspace>/studios/<studio>/<directory-path>" in result_text


def test_ls_impl_local_path_raises_error():
    """Test that path without the prefix 'lit://' raises ValueError."""
    with pytest.raises(ValueError, match="Path must be a Studio path starting with 'lit://'."):
        ls_impl(path="local/path")

    with pytest.raises(ValueError, match="Path must be a Studio path starting with 'lit://'."):
        ls_impl(path="local/lit://path")


def test_ls_impl_nonexistent_path_raises_error():
    """Test that providing a nonexistent studio path raises FileNotFoundError."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "nonexistent/path",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {"exists": False}

    with (
        patch("lightning_sdk.cli.studio.ls.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.ls.resolve_studio", return_value=mock_selected_studio),
        pytest.raises(FileNotFoundError, match="The provided path does not exist in the studio"),
    ):
        ls_impl(path="lit://test-owner/test-teamspace/studios/test-studio/nonexistent/path")


def test_ls_impl_file_path_prints_filename(capsys):
    """Test that providing a file path prints just the filename."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "data/file.txt",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {
        "exists": True,
        "type": "file",
        "size": 1024,
    }

    with (
        patch("lightning_sdk.cli.studio.ls.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.ls.resolve_studio", return_value=mock_selected_studio),
    ):
        ls_impl(path="lit://test-owner/test-teamspace/studios/test-studio/data/file.txt")

        captured = capsys.readouterr()
        assert captured.out.strip() == "data/file.txt"


def test_ls_impl_directory_lists_contents(capsys):
    """Test that providing a directory path lists its contents."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "data",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {
        "exists": True,
        "type": "directory",
        "size": None,
    }

    mock_tree = {
        "tree": [
            {"path": "file1.txt", "type": "blob", "size": 100},
            {"path": "file2.txt", "type": "blob", "size": 200},
            {"path": "subfolder", "type": "tree"},
        ]
    }

    mock_selected_studio._studio_api.get_tree.return_value = mock_tree

    with (
        patch("lightning_sdk.cli.studio.ls.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.ls.resolve_studio", return_value=mock_selected_studio),
    ):
        ls_impl(path="lit://test-owner/test-teamspace/studios/test-studio/data")

        captured = capsys.readouterr()
        output_lines = captured.out.strip().split("\n")

        assert "file1.txt" in output_lines
        assert "file2.txt" in output_lines
        assert "subfolder/" in output_lines


def test_ls_impl_root_directory(capsys):
    """Test listing the root directory of a studio."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {
        "exists": True,
        "type": "directory",
        "size": None,
    }

    mock_tree = {
        "tree": [
            {"path": "data", "type": "tree"},
            {"path": "models", "type": "tree"},
            {"path": "README.md", "type": "blob", "size": 500},
        ]
    }

    mock_selected_studio._studio_api.get_tree.return_value = mock_tree

    with (
        patch("lightning_sdk.cli.studio.ls.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.ls.resolve_studio", return_value=mock_selected_studio),
    ):
        ls_impl(path="lit://test-owner/test-teamspace/studios/test-studio/")

        captured = capsys.readouterr()
        output_lines = captured.out.strip().split("\n")

        assert "data/" in output_lines
        assert "models/" in output_lines
        assert "README.md" in output_lines


def test_ls_studio_integration(capsys):
    """Test the full ls_studio command integration."""
    runner = CliRunner()

    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "data",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {
        "exists": True,
        "type": "directory",
        "size": None,
    }

    mock_tree = {
        "tree": [
            {"path": "file1.txt", "type": "blob", "size": 100},
            {"path": "subfolder", "type": "tree"},
        ]
    }

    mock_selected_studio._studio_api.get_tree.return_value = mock_tree

    with (
        patch("lightning_sdk.cli.studio.ls.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.ls.resolve_studio", return_value=mock_selected_studio),
    ):
        result = runner.invoke(ls_studio, ["lit://test-owner/test-teamspace/studios/test-studio/data"])

        assert result.exit_code == 0
        assert "file1.txt" in result.output
        assert "subfolder/" in result.output


def test_ls_impl_nested_path(capsys):
    """Test listing a deeply nested directory path."""
    mock_parse_result = {
        "studio": "test-studio",
        "teamspace": "test-teamspace",
        "owner": "test-owner",
        "destination": "data/processed/2024",
    }

    mock_selected_studio = MagicMock()
    mock_selected_studio.name = "test-studio"
    mock_selected_studio.teamspace.name = "test-teamspace"
    mock_selected_studio._studio.id = "studio-id"
    mock_selected_studio._teamspace.id = "teamspace-id"

    mock_selected_studio._studio_api.get_path_info.return_value = {
        "exists": True,
        "type": "directory",
        "size": None,
    }

    mock_tree = {
        "tree": [
            {"path": "january.csv", "type": "blob", "size": 1000},
            {"path": "february.csv", "type": "blob", "size": 1100},
        ]
    }

    mock_selected_studio._studio_api.get_tree.return_value = mock_tree

    with (
        patch("lightning_sdk.cli.studio.ls.parse_studio_path", return_value=mock_parse_result),
        patch("lightning_sdk.cli.studio.ls.resolve_studio", return_value=mock_selected_studio),
    ):
        ls_impl(path="lit://test-owner/test-teamspace/studios/test-studio/data/processed/2024")

        captured = capsys.readouterr()
        output_lines = captured.out.strip().split("\n")

        assert "january.csv" in output_lines
        assert "february.csv" in output_lines
