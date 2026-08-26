from unittest import mock

import pytest

from lightning_sdk.cli.ls import ls_impl
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_ls_help() -> None:
    assert_help_contains(
        "lightning ls --help",
        "Usage: lightning ls [OPTIONS] PATH",
        "List contents of a teamspace drive directory.",
    )


def _fake_teamspace():
    ts = mock.MagicMock()
    ts.id = "ts-123"
    return ts


def test_ls_prints_entries_with_directory_suffix(capsys) -> None:
    def list_files(teamspace_id, path, recursive):
        if path == "artifacts":
            # parent listing, used for the existence check
            return [{"path": "reports", "type": "tree"}]
        assert path == "artifacts/reports"
        return [
            {"path": "2024", "type": "tree"},
            {"path": "summary.html", "type": "blob", "size": 10},
        ]

    with mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace", return_value=_fake_teamspace()), mock.patch(
        "lightning_sdk.cli.ls.FilesystemApi"
    ) as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        ls_impl("lit://my-org/my-teamspace/artifacts/reports")

    assert capsys.readouterr().out.splitlines() == ["2024/", "summary.html"]


def test_ls_file_prints_its_path(capsys) -> None:
    def list_files(teamspace_id, path, recursive):
        return [{"path": "summary.html", "type": "blob", "size": 10}]

    with mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace", return_value=_fake_teamspace()), mock.patch(
        "lightning_sdk.cli.ls.FilesystemApi"
    ) as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        ls_impl("lit://my-org/my-teamspace/artifacts/summary.html")

    assert capsys.readouterr().out.splitlines() == ["artifacts/summary.html"]


def test_ls_missing_path_raises() -> None:
    with mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace", return_value=_fake_teamspace()), mock.patch(
        "lightning_sdk.cli.ls.FilesystemApi"
    ) as mock_api_cls:
        mock_api_cls.return_value.list_files.return_value = []
        with pytest.raises(FileNotFoundError, match="does not exist"):
            ls_impl("lit://my-org/my-teamspace/artifacts/missing")


def test_ls_requires_lit_url() -> None:
    with pytest.raises(ValueError, match="lit://"):
        ls_impl("artifacts/reports")


def test_ls_json_outputs_entries(capsys) -> None:
    import json

    def list_files(teamspace_id, path, recursive):
        if path == "artifacts":
            return [{"path": "reports", "type": "tree"}]
        return [
            {"path": "2024", "type": "tree"},
            {"path": "summary.html", "type": "blob", "size": 10, "clusterId": "cluster-a"},
        ]

    with mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace", return_value=_fake_teamspace()), mock.patch(
        "lightning_sdk.cli.ls.FilesystemApi"
    ) as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        ls_impl("lit://my-org/my-teamspace/artifacts/reports", as_json=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload == [
        {"path": "2024", "type": "tree"},
        {"path": "summary.html", "type": "blob", "size": 10, "clusterId": "cluster-a"},
    ]


def test_ls_json_file_outputs_its_entry(capsys) -> None:
    import json

    def list_files(teamspace_id, path, recursive):
        return [{"path": "summary.html", "type": "blob", "size": 10, "clusterId": "cluster-a"}]

    with mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace", return_value=_fake_teamspace()), mock.patch(
        "lightning_sdk.cli.ls.FilesystemApi"
    ) as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        ls_impl("lit://my-org/my-teamspace/artifacts/summary.html", as_json=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload == [{"path": "summary.html", "type": "blob", "size": 10, "clusterId": "cluster-a"}]


def test_ls_recursive_lists_full_relative_paths(capsys) -> None:
    def list_files(teamspace_id, path, recursive):
        if path == "artifacts":
            return [{"path": "reports", "type": "tree"}]
        assert path == "artifacts/reports"
        if recursive:
            return [
                {"path": "summary.html", "type": "blob", "size": 10},
                {"path": "img/chart.png", "type": "blob", "size": 20},
            ]
        raise AssertionError("expected a recursive listing")

    with mock.patch("lightning_sdk.cli.utils.filesystem.resolve_teamspace", return_value=_fake_teamspace()), mock.patch(
        "lightning_sdk.cli.ls.FilesystemApi"
    ) as mock_api_cls:
        mock_api_cls.return_value.list_files.side_effect = list_files
        ls_impl("lit://my-org/my-teamspace/artifacts/reports", recursive=True)

    assert capsys.readouterr().out.splitlines() == ["summary.html", "img/chart.png"]
