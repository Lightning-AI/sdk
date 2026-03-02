from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.cli.cp import route_cp_operation


def test_route_cp_lightning_storage_download():
    """Test that lightning_storage download routes to Filesystem.copy."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="lit://my-org/my-teamspace/lightning_storage/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/lightning_storage/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
        )


def test_route_cp_lightning_storage_download_recursive():
    """Test that lightning_storage download passes recursive=True to Filesystem.copy."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="lit://my-org/my-teamspace/lightning_storage/data/mydir",
            destination="/local/mydir",
            recursive=True,
        )

        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/lightning_storage/data/mydir",
            destination="/local/mydir",
            recursive=True,
        )


def test_route_cp_lightning_storage_raises_if_both_remote():
    """Test that two lit:// paths raises ValueError."""
    with pytest.raises(ValueError, match="two remote URLs"):
        route_cp_operation(
            source="lit://my-org/my-teamspace/lightning_storage/a.txt",
            destination="lit://my-org/my-teamspace/lightning_storage/b.txt",
        )


def test_route_cp_lightning_storage_raises_if_both_local():
    """Test that two local paths raises ValueError."""
    with pytest.raises(ValueError, match="At least one path"):
        route_cp_operation(
            source="/local/a.txt",
            destination="/local/b.txt",
        )


def test_route_cp_uploads_download():
    """Test that uploads download routes to Filesystem.copy and replaces uploads/ with Uploads/."""
    mock_fs = MagicMock()
    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="lit://my-org/my-teamspace/uploads/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
        )
        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/Uploads/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
        )


def test_route_cp_uploads_download_recursive():
    """Test that uploads download passes recursive=True to Filesystem.copy."""
    mock_fs = MagicMock()
    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="lit://my-org/my-teamspace/uploads/data/mydir",
            destination="/local/mydir",
            recursive=True,
        )
        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/Uploads/data/mydir",
            destination="/local/mydir",
            recursive=True,
        )
