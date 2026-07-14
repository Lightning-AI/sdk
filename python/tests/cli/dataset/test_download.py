from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_dataset_download_help() -> None:
    assert_help_contains(
        "lightning dataset download --help",
        "Usage: lightning dataset download",
        "Download a dataset version as a zip file.",
        "NAME must be a Lightning path:",
    )


@mock_command_logging
def test_datasets_download_help() -> None:
    assert_help_contains(
        "lightning datasets download --help",
        "Usage: lightning datasets download",
        "Download a dataset version as a zip file.",
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
    from tests.cli.help import command_text

    text = command_text("lightning dataset download badname")
    assert "NAME must be a Lightning path" in text
