from unittest import mock

import pytest

from lightning_sdk.cli.rm import rm_impl
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_rm_help() -> None:
    assert_help_contains(
        "lightning rm --help",
        "Usage: lightning rm [OPTIONS] PATH",
        "Remove a file or directory from a teamspace drive.",
    )


def test_rm_delegates_to_filesystem() -> None:
    with mock.patch("lightning_sdk.cli.rm.Filesystem") as mock_fs_cls:
        rm_impl("lit://my-org/my-teamspace/uploads/data", recursive=True)

    mock_fs_cls.return_value.rm.assert_called_once_with("lit://my-org/my-teamspace/uploads/data", recursive=True)


def test_rm_force_ignores_missing_paths() -> None:
    with mock.patch("lightning_sdk.cli.rm.Filesystem") as mock_fs_cls:
        mock_fs_cls.return_value.rm.side_effect = FileNotFoundError("no such file")
        rm_impl("lit://my-org/my-teamspace/uploads/missing.txt", force=True)


def test_rm_missing_path_fails_without_force() -> None:
    with mock.patch("lightning_sdk.cli.rm.Filesystem") as mock_fs_cls:
        mock_fs_cls.return_value.rm.side_effect = FileNotFoundError("no such file")
        with pytest.raises(FileNotFoundError):
            rm_impl("lit://my-org/my-teamspace/uploads/missing.txt")


def test_rm_requires_lit_url() -> None:
    with pytest.raises(ValueError, match="lit://"):
        rm_impl("uploads/data")
