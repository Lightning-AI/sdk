from unittest.mock import patch

from click.testing import CliRunner

from lightning_sdk.cli.legacy import start as start_cli
from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_start_studio():
    result_text = command_text("lightning studio start --help")

    assert "Usage: lightning studio start [OPTIONS]" in result_text
    assert "Start a Studio" in result_text
    assert "--name" in result_text
    assert "--teamspace" in result_text
    assert "--create" in result_text
    assert "--machine" in result_text
    assert "--interruptible" in result_text
    assert "--cloud" in result_text
    assert "--cloud-provider" not in result_text
    assert "--cloud-account" not in result_text
    assert "--gpus" in result_text


@mock_command_logging
def test_studios_start_help() -> None:
    assert_help_contains("lightning studios start --help", "Usage: lightning studios start", "Start a Studio")


@mock_command_logging
def test_start_help() -> None:
    text = assert_help_contains(
        "lightning start --help",
        "`lightning start` has moved to noun-first commands:",
        "studio -> lightning studio start",
    )
    assert "Deprecation warning:" not in text


@mock_command_logging
def test_start_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning start studio --help",
        "Deprecation warning:",
        "Use `lightning studio start` instead of `lightning start studio`.",
        "Usage: lightning start studio [OPTIONS]",
    )


@patch("lightning_sdk.cli.legacy.start.Studio")
@mock_command_logging
def test_start_cli(mock_studio_class):
    mock_studio_instance = mock_studio_class.return_value
    mock_studio_instance.start.side_effect = Exception("Studio not found")

    runner = CliRunner()
    result = runner.invoke(start_cli.studio, ["test", "--teamspace", "aniket/test"])

    assert result.exit_code != 0
    assert "Studio not found" in str(result.exception)
