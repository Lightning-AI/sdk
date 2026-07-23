from types import SimpleNamespace
from unittest import mock

import pytest
from click.testing import CliRunner

from lightning_sdk.cli.dataset.download import download_dataset_cmd
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_dataset_download_help() -> None:
    assert_help_contains(
        "lightning dataset download --help",
        "Usage: lightning dataset download",
        "Download a dataset version.",
        "NAME must be a Lightning path:",
        "--unzip",
    )


@mock_command_logging
def test_datasets_download_help() -> None:
    assert_help_contains(
        "lightning datasets download --help",
        "Usage: lightning datasets download",
        "Download a dataset version.",
    )


@mock_command_logging
def test_download_dataset_legacy_help() -> None:
    assert_help_contains(
        "lightning download dataset --help",
        "Deprecation warning:",
        "Use `lightning dataset download` instead of `lightning download dataset`.",
        "Usage: lightning download dataset [OPTIONS] NAME",
    )


@mock_command_logging
def test_dataset_download_invalid_name() -> None:
    import pytest

    from tests.cli.help import command_text

    with pytest.raises(ValueError, match="NAME must be a Lightning path"):
        command_text("lightning dataset download badname")


@pytest.mark.parametrize(
    ("args", "unzip"),
    [
        ([], False),
        (["--unzip"], True),
    ],
)
def test_dataset_download_unzip_flag_passthrough(args, unzip) -> None:
    info = SimpleNamespace(name="my-dataset", version="v1", path="/tmp/my-dataset_v1")
    with mock.patch("lightning_sdk.cli.dataset.download.download_dataset", return_value=info) as download:
        result = CliRunner().invoke(
            download_dataset_cmd,
            ["my-org/my-teamspace/my-dataset", *args],
        )

    assert result.exit_code == 0, result.output
    download.assert_called_once_with(
        name="my-org/my-teamspace/my-dataset",
        target_path=".",
        cluster_id=None,
        unzip=unzip,
    )
    assert "Downloaded dataset 'my-dataset' version 'v1' to /tmp/my-dataset_v1" in result.output
