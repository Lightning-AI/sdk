from unittest.mock import MagicMock, patch

import pytest

from lightning_sdk.cli.cp import route_cp_operation


@pytest.mark.parametrize("resource_type", ["studios", "r2_connections", "artifacts", "unknown_resource"])
def test_route_cp_passes_any_resource_type_through(resource_type):
    """Every resource type routes to the drive; the server decides what exists."""
    mock_fs = MagicMock()
    source = f"lit://my-org/my-teamspace/{resource_type}/data/model.ckpt"

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source=source,
            destination="/local/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source=source,
            destination="/local/model.ckpt",
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_raises_if_both_local():
    """Test that two local paths raises ValueError."""
    with pytest.raises(ValueError, match="At least one path"):
        route_cp_operation(
            source="/local/a.txt",
            destination="/local/b.txt",
        )


def test_route_cp_raises_for_invalid_short_lit_url():
    """Test that malformed short lit URLs still raise a clear ValueError."""
    with pytest.raises(ValueError, match="Invalid lit URL format"):
        route_cp_operation(
            source="lit://my-org/my-teamspace",
            destination="/local/model.ckpt",
        )


def test_route_cp_raises_if_destination_is_missing():
    """Test that missing destination raises a clear ValueError."""
    with pytest.raises(ValueError, match="Destination path must be provided"):
        route_cp_operation(
            source="/local/a.txt",
            destination=None,
        )


NAMED_RESOURCE_TYPES = [
    ("s3_folders", "my-bucket"),
    ("lightning_storage", "my-storage"),
    ("s3_connections", "my-s3-connection"),
    ("jobs", "my-job"),
    ("gcs_folders", "my-gcs-folder"),
    ("gcs_connections", "my-gcs-connection"),
]


@pytest.mark.parametrize(("resource_type", "resource_name"), NAMED_RESOURCE_TYPES)
def test_route_cp_download(resource_type, resource_name):
    """Test that download routes to Filesystem.copy for each resource type."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        source = f"lit://my-org/my-teamspace/{resource_type}/{resource_name}/data/model.ckpt"
        destination = "/local/model.ckpt"

        route_cp_operation(source=source, destination=destination, recursive=False)

        mock_fs.copy.assert_called_once_with(
            source=source,
            destination=destination,
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


@pytest.mark.parametrize(("resource_type", "resource_name"), NAMED_RESOURCE_TYPES)
def test_route_cp_download_recursive(resource_type, resource_name):
    """Test that download passes recursive=True to Filesystem.copy."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        source = f"lit://my-org/my-teamspace/{resource_type}/{resource_name}/data/mydir"
        destination = "/local/mydir"

        route_cp_operation(source=source, destination=destination, recursive=True)

        mock_fs.copy.assert_called_once_with(
            source=source,
            destination=destination,
            recursive=True,
            progress_bar=True,
            cloud_account=None,
        )


@pytest.mark.parametrize(("resource_type", "resource_name"), NAMED_RESOURCE_TYPES)
def test_route_cp_raises_if_both_remote(resource_type, resource_name):
    """Test that two lit:// paths raises ValueError."""
    with pytest.raises(ValueError, match="two remote URLs"):
        route_cp_operation(
            source=f"lit://my-org/my-teamspace/{resource_type}/{resource_name}/a.txt",
            destination=f"lit://my-org/my-teamspace/{resource_type}/{resource_name}/b.txt",
        )


def test_route_cp_uploads_download():
    """Test that uploads download passes the source through unmodified."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="lit://my-org/my-teamspace/uploads/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/uploads/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_uploads_download_recursive():
    """Test that uploads download passes recursive=True through."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="lit://my-org/my-teamspace/uploads/data/mydir",
            destination="/local/mydir",
            recursive=True,
        )

        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/uploads/data/mydir",
            destination="/local/mydir",
            recursive=True,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_download_passes_paths_with_uploads_segment_through():
    """Test that a nested uploads segment in another namespace is left alone."""
    mock_fs = MagicMock()
    source = "lit://my-org/my-teamspace/lightning_storage/my-storage/uploads/model.ckpt"

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source=source,
            destination="/local/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source=source,
            destination="/local/model.ckpt",
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_download_canonicalizes_mixed_case_resource_type():
    """Test that mixed-case remote resource types are canonicalized before download dispatch."""
    mock_fs = MagicMock()
    source = "lit://my-org/my-teamspace/Lightning_Storage/my-storage/data/model.ckpt"

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source=source,
            destination="/local/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source="lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt",
            destination="/local/model.ckpt",
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_lightning_storage_upload():
    """Test that lightning_storage upload routes to Filesystem.copy."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="/local/model.ckpt",
            destination="lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source="/local/model.ckpt",
            destination="lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt",
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_lightning_storage_upload_canonicalizes_mixed_case_resource_type():
    """Test that mixed-case upload resource types are canonicalized before Filesystem.copy."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="/local/model.ckpt",
            destination="lit://my-org/my-teamspace/Lightning_Storage/my-storage/data/model.ckpt",
            recursive=False,
        )

        mock_fs.copy.assert_called_once_with(
            source="/local/model.ckpt",
            destination="lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt",
            recursive=False,
            progress_bar=True,
            cloud_account=None,
        )


def test_route_cp_lightning_storage_upload_passes_progress_bar():
    """Test that lightning_storage upload preserves progress_bar for Filesystem.copy."""
    mock_fs = MagicMock()

    with patch("lightning_sdk.cli.cp.Filesystem", return_value=mock_fs):
        route_cp_operation(
            source="/local/model.ckpt",
            destination="lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt",
            recursive=False,
            progress_bar=False,
        )

        mock_fs.copy.assert_called_once_with(
            source="/local/model.ckpt",
            destination="lit://my-org/my-teamspace/lightning_storage/my-storage/data/model.ckpt",
            recursive=False,
            progress_bar=False,
            cloud_account=None,
        )
