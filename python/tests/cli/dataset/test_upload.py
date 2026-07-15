from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_dataset_upload_help() -> None:
    assert_help_contains(
        "lightning dataset upload --help",
        "Usage: lightning dataset upload",
        "Upload a dataset to Lightning Datasets.",
        "NAME must be a Lightning path:",
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
