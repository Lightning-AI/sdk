from unittest import mock

import pytest

from lightning_sdk.filesystem import Filesystem

TEAMSPACE_ID = "ts-123"
LIT_URL = "lit://my-org/my-teamspace/uploads/data/test1.txt"
DIR_URL = "lit://my-org/my-teamspace/uploads/data"


@pytest.fixture()
def fake_teamspace():
    ts = mock.MagicMock()
    ts.id = TEAMSPACE_ID
    return ts


def test_rm_file_deletes_it(fake_teamspace):
    def list_files(teamspace_id, path, recursive):
        assert path == "uploads/data"
        return [{"path": "test1.txt", "type": "blob", "size": 3}]

    with mock.patch("lightning_sdk.filesystem.resolve_teamspace", return_value=fake_teamspace), mock.patch(
        "lightning_sdk.filesystem.parse_lit_url",
        return_value={"teamspace": "my-teamspace", "owner": "my-org", "destination": "uploads/data/test1.txt"},
    ), mock.patch("lightning_sdk.filesystem.FilesystemApi") as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        Filesystem().rm(LIT_URL)

    mock_api_cls.return_value.delete_file.assert_called_once_with(TEAMSPACE_ID, "uploads/data/test1.txt")
    mock_api_cls.return_value.delete_folder.assert_not_called()


def test_rm_directory_requires_recursive(fake_teamspace):
    def list_files(teamspace_id, path, recursive):
        return [{"path": "data", "type": "tree"}]

    with mock.patch("lightning_sdk.filesystem.resolve_teamspace", return_value=fake_teamspace), mock.patch(
        "lightning_sdk.filesystem.parse_lit_url",
        return_value={"teamspace": "my-teamspace", "owner": "my-org", "destination": "uploads/data"},
    ), mock.patch("lightning_sdk.filesystem.FilesystemApi") as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        with pytest.raises(ValueError, match="is a directory"):
            Filesystem().rm(DIR_URL)

    mock_api_cls.return_value.delete_folder.assert_not_called()


def test_rm_directory_recursive_deletes_the_folder(fake_teamspace):
    def list_files(teamspace_id, path, recursive):
        return [{"path": "data", "type": "tree"}]

    with mock.patch("lightning_sdk.filesystem.resolve_teamspace", return_value=fake_teamspace), mock.patch(
        "lightning_sdk.filesystem.parse_lit_url",
        return_value={"teamspace": "my-teamspace", "owner": "my-org", "destination": "uploads/data"},
    ), mock.patch("lightning_sdk.filesystem.FilesystemApi") as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        Filesystem().rm(DIR_URL, recursive=True)

    mock_api_cls.return_value.delete_folder.assert_called_once_with(TEAMSPACE_ID, "uploads/data")
    mock_api_cls.return_value.delete_file.assert_not_called()


def test_rm_missing_path_raises(fake_teamspace):
    with mock.patch("lightning_sdk.filesystem.resolve_teamspace", return_value=fake_teamspace), mock.patch(
        "lightning_sdk.filesystem.parse_lit_url",
        return_value={"teamspace": "my-teamspace", "owner": "my-org", "destination": "uploads/data/missing.txt"},
    ), mock.patch("lightning_sdk.filesystem.FilesystemApi") as mock_api_cls:
        mock_api_cls.return_value.list_files.return_value = []
        with pytest.raises(FileNotFoundError, match="missing.txt"):
            Filesystem().rm("lit://my-org/my-teamspace/uploads/data/missing.txt")


def test_rm_refuses_teamspace_root(fake_teamspace):
    with mock.patch("lightning_sdk.filesystem.resolve_teamspace", return_value=fake_teamspace), mock.patch(
        "lightning_sdk.filesystem.parse_lit_url",
        return_value={"teamspace": "my-teamspace", "owner": "my-org", "destination": ""},
    ), mock.patch("lightning_sdk.filesystem.FilesystemApi"), pytest.raises(ValueError, match="teamspace root"):
        Filesystem().rm("lit://my-org/my-teamspace/", recursive=True)
