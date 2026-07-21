from unittest import mock

from click.testing import CliRunner

from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_dataset_upload_help() -> None:
    assert_help_contains(
        "lightning dataset upload --help",
        "Usage: lightning dataset upload",
        "Upload a dataset to Lightning Datasets.",
        "NAME must be a Lightning path:",
        "--zip",
    )


@mock_command_logging
def test_datasets_upload_help() -> None:
    assert_help_contains(
        "lightning datasets upload --help",
        "Usage: lightning datasets upload",
        "Upload a dataset to Lightning Datasets.",
    )


@mock_command_logging
def test_dataset_upload_invalid_name() -> None:
    import pytest

    from lightning_sdk.datasets import upload_dataset

    with pytest.raises(ValueError, match="NAME must be a Lightning path"):
        upload_dataset(name="badname", path=".")


def test_dataset_upload_zip_flag_passthrough() -> None:
    from lightning_sdk.cli.dataset.upload import upload_dataset_cmd
    from lightning_sdk.datasets import UploadedDatasetInfo

    uploaded = UploadedDatasetInfo(name="my-dataset", version="v1", teamspace="my-teamspace")
    with mock.patch("lightning_sdk.cli.dataset.upload.upload_dataset", return_value=uploaded) as upload:
        result = CliRunner().invoke(
            upload_dataset_cmd,
            ["my-org/my-teamspace/my-dataset", ".", "--zip"],
        )

    assert result.exit_code == 0, result.output
    upload.assert_called_once_with(
        name="my-org/my-teamspace/my-dataset",
        path=".",
        cloud_account=None,
        as_zip=True,
    )
