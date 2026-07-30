from unittest.mock import MagicMock, patch

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.mmt import register_commands
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_mmt_delete_help() -> None:
    assert_help_contains(
        "lightning mmt delete --help",
        "Usage: lightning mmt delete [OPTIONS] NAME",
        "Delete a multi-machine job.",
        "--yes",
        "-y",
    )


def test_delete_mmt_uses_shared_command() -> None:
    resource = MagicMock()
    with patch("lightning_sdk.mmt.MMT", return_value=resource) as mmt_cls:
        group = click.Group()
        register_commands(group)
        result = CliRunner().invoke(group, ["delete", "my-mmt", "-y"])

    assert result.exit_code == 0
    assert result.output == "Multi-machine job deleted\n"
    mmt_cls.assert_called_once_with(name="my-mmt", teamspace=None)
    resource.delete.assert_called_once_with()


@mock_command_logging
def test_mmts_delete_help() -> None:
    assert_help_contains(
        "lightning mmts delete --help",
        "Usage: lightning mmts delete [OPTIONS] NAME",
        "Delete a multi-machine job.",
        "--yes",
        "-y",
    )


@mock_command_logging
def test_delete_mmt_legacy_help() -> None:
    assert_help_contains(
        "lightning delete mmt --help",
        "Deprecation warning:",
        "Use `lightning mmt delete` instead of `lightning delete mmt`.",
        "Usage: lightning delete mmt [OPTIONS] NAME",
        "--yes",
        "-y",
    )
