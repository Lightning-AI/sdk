from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.cli.studio.cp import cp_impl
from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_cp_help():
    result_text = command_text("lightning studio cp --help")

    assert "Usage: lightning studio cp [OPTIONS] SOURCE DESTINATION" in result_text
    assert "Copy a Studio file." in result_text
    assert "lit://<owner>/<my-teamspace>/studios/<my-studio>/<filepath>" in result_text
    assert "--recursive  -r" in result_text


@mock_command_logging
def test_studios_cp_help() -> None:
    assert_help_contains("lightning studios cp --help", "Usage: lightning studios cp", "Copy a Studio file.")


@mock_command_logging
def test_cp_impl_both_studio_files_raises_error():
    """Test that providing both source and destination as Studio files raises an error."""
    with pytest.raises(ValueError, match="Both source and destination cannot be Studio files"):
        cp_impl(
            source="lit://owner/teamspace/studios/studio1/file1.txt",
            destination="lit://owner/teamspace/studios/studio2/file2.txt",
        )


@mock_command_logging
def test_cp_impl_both_local_files_raises_error():
    """Test that providing both source and destination as local files raises an error."""
    with pytest.raises(ValueError, match="Either source or destination must be a Studio file"):
        cp_impl(source="local_file1.txt", destination="local_file2.txt")


def _mock_studio():
    studio = MagicMock()
    studio.name = "test-studio"
    studio.teamspace.name = "test-teamspace"
    studio.owner.name = "test-owner"
    return studio


_FULL_URL = "lit://test-owner/test-teamspace/studios/test-studio/remote_file.txt"


@pytest.mark.parametrize(
    "studio_path",
    [
        _FULL_URL,
        # short forms: owner, or owner and teamspace, resolve from defaults
        "lit://test-teamspace/studios/test-studio/remote_file.txt",
        "lit://test-studio/remote_file.txt",
    ],
)
@mock_command_logging
def test_cp_upload_delegates_to_generic_copy(studio_path, tmp_path: Path):
    """Every accepted URL form resolves to the fully-qualified drive URL and delegates to Filesystem.copy."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")
    mock_fs = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.cp.resolve_studio", return_value=_mock_studio()) as resolve_mock,
        patch("lightning_sdk.cli.studio.cp.Filesystem", return_value=mock_fs),
        patch("lightning_sdk.cli.studio.cp.Console"),
    ):
        cp_impl(source=str(test_file), destination=studio_path)

    resolve_mock.assert_called_once()
    mock_fs.copy.assert_called_once_with(source=str(test_file), destination=_FULL_URL, recursive=False)


@mock_command_logging
def test_cp_download_delegates_to_generic_copy(tmp_path: Path):
    test_file = tmp_path / "test_file.txt"
    mock_fs = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.cp.resolve_studio", return_value=_mock_studio()),
        patch("lightning_sdk.cli.studio.cp.Filesystem", return_value=mock_fs),
        patch("lightning_sdk.cli.studio.cp.Console"),
    ):
        cp_impl(source=_FULL_URL, destination=str(test_file), recursive=False)

    mock_fs.copy.assert_called_once_with(source=_FULL_URL, destination=str(test_file), recursive=False)


@mock_command_logging
def test_cp_download_preserves_trailing_slash_for_directory_targets(tmp_path: Path):
    """A trailing slash marks a directory target; the drive URL keeps it."""
    mock_fs = MagicMock()

    with (
        patch("lightning_sdk.cli.studio.cp.resolve_studio", return_value=_mock_studio()),
        patch("lightning_sdk.cli.studio.cp.Filesystem", return_value=mock_fs),
        patch("lightning_sdk.cli.studio.cp.Console"),
    ):
        cp_impl(source="lit://test-studio/", destination=str(tmp_path), recursive=True)

    mock_fs.copy.assert_called_once_with(
        source="lit://test-owner/test-teamspace/studios/test-studio/",
        destination=str(tmp_path),
        recursive=True,
    )


@mock_command_logging
def test_cp_studio_root_without_trailing_slash_raises():
    with pytest.raises(ValueError, match="add a trailing '/'"):
        cp_impl(source="lit://owner/teamspace/studios/my-studio", destination="/local/out")
