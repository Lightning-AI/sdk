from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_dataset_upload_help() -> None:
    assert_help_contains(
        "lightning dataset upload --help",
        "Usage: lightning dataset upload",
        "Upload a file as a dataset version.",
        "NAME must be a Lightning path:",
    )


@mock_command_logging
def test_datasets_upload_help() -> None:
    assert_help_contains(
        "lightning datasets upload --help",
        "Usage: lightning datasets upload",
        "Upload a file as a dataset version.",
    )


@mock_command_logging
def test_upload_dataset_legacy_help() -> None:
    assert_help_contains(
        "lightning upload dataset --help",
        "Deprecation warning:",
        "Use `lightning dataset upload` instead of `lightning upload dataset`.",
        "Usage: lightning upload dataset [OPTIONS] NAME",
    )


@mock_command_logging
def test_dataset_upload_invalid_name() -> None:
    from tests.cli.help import command_text

    text = command_text("lightning dataset upload badname --source-path /dev/null")
    assert "NAME must be a Lightning path" in text
