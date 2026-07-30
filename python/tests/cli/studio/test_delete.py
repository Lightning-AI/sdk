from unittest.mock import MagicMock, patch

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.studio import register_commands
from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_delete_studio():
    result_text = command_text("lightning studio delete --help")

    assert "Usage: lightning studio delete [OPTIONS] NAME" in result_text
    assert "Delete a Studio." in result_text
    assert "--name" not in result_text
    assert "--teamspace" in result_text
    assert "--yes" in result_text
    assert "-y" in result_text


def test_delete_studio_uses_positional_name_and_yes_flag() -> None:
    resource = MagicMock()
    with patch("lightning_sdk.studio.Studio", return_value=resource) as studio_cls:
        group = click.Group()
        register_commands(group)
        result = CliRunner().invoke(group, ["delete", "my-studio", "-y"])

    assert result.exit_code == 0
    assert result.output == "Studio deleted\n"
    studio_cls.assert_called_once_with(name="my-studio", teamspace=None, create_ok=False)
    resource.delete.assert_called_once_with()


@mock_command_logging
def test_studios_delete_help() -> None:
    assert_help_contains("lightning studios delete --help", "Usage: lightning studios delete", "Delete a Studio.")


@mock_command_logging
def test_delete_studio_legacy_help() -> None:
    assert_help_contains(
        "lightning delete studio --help",
        "Deprecation warning:",
        "Use `lightning studio delete` instead of `lightning delete studio`.",
        "Usage: lightning delete studio [OPTIONS]",
    )
