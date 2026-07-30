from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.container import register_commands
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_container_delete_help() -> None:
    text = assert_help_contains(
        "lightning container delete --help",
        "Usage: lightning container delete",
        "Delete the docker container NAME.",
    )
    normalized_text = " ".join(text.replace("│", " ").split())
    assert "Defaults to the configured teamspace." in normalized_text
    assert "interactive menu" not in normalized_text


@mock_command_logging
def test_containers_delete_help() -> None:
    assert_help_contains(
        "lightning containers delete --help", "Usage: lightning containers delete", "Delete the docker container NAME."
    )


@mock_command_logging
def test_delete_container_legacy_help() -> None:
    assert_help_contains(
        "lightning delete container --help",
        "Deprecation warning:",
        "Use `lightning container delete` instead of `lightning delete container`.",
        "Usage: lightning delete container [OPTIONS] NAME",
    )


def test_delete_container_uses_shared_command() -> None:
    api = MagicMock()
    resolved_teamspace = SimpleNamespace(
        name="teamspace",
        owner=SimpleNamespace(name="owner"),
    )

    with (
        patch("lightning_sdk.cli.container.delete.LitContainer", return_value=api, create=True) as api_cls,
        patch(
            "lightning_sdk.cli.container.delete.TeamspacesMenu",
            return_value=MagicMock(return_value=resolved_teamspace),
            create=True,
        ),
    ):
        group = click.Group()
        register_commands(group)
        result = CliRunner().invoke(group, ["delete", "image", "-y"])

    assert result.exit_code == 0
    assert result.output == "Container deleted\n"
    api_cls.assert_called_once_with()
    api.delete_container.assert_called_once_with("image", "teamspace", "owner")
