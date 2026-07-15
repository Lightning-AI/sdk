from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_dataset_download_help() -> None:
    assert_help_contains(
        "lightning dataset download --help",
        "Usage: lightning dataset download",
        "Download a dataset version.",
        "NAME must be a Lightning path:",
        "--zip",
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
