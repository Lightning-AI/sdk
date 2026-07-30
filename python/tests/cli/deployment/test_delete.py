from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import rich_click as click
from click.testing import CliRunner

from lightning_sdk.cli.deployment import register_commands
from tests.cli.help import assert_help_contains, mock_command_logging


@mock_command_logging
def test_delete_deployment_help() -> None:
    assert_help_contains(
        "lightning deployment delete --help",
        "Usage: lightning deployment delete [OPTIONS] NAME",
        "Delete a deployment.",
        "--yes",
        "-y",
    )


@mock_command_logging
def test_delete_deployments_alias_help() -> None:
    assert_help_contains(
        "lightning deployments delete --help",
        "Usage: lightning deployments delete [OPTIONS] NAME",
        "Delete a deployment.",
        "--yes",
        "-y",
    )


def test_delete_deployment_uses_shared_command() -> None:
    api = MagicMock()
    teamspace = SimpleNamespace(id="teamspace-1")
    deployment = SimpleNamespace(name="demo")

    with (
        patch("lightning_sdk.cli.deployment.delete.DeploymentApi", return_value=api) as api_cls,
        patch("lightning_sdk.cli.deployment.delete.resolve_teamspace", return_value=teamspace),
        patch("lightning_sdk.cli.deployment.delete.resolve_deployment", return_value=deployment) as resolve_deployment,
    ):
        group = click.Group()
        register_commands(group)
        result = CliRunner().invoke(group, ["delete", "demo", "-y"])

    assert result.exit_code == 0
    assert result.output == "Deployment deleted\n"
    api_cls.assert_called_once_with()
    resolve_deployment.assert_called_once_with(api, "teamspace-1", "demo")
    api.delete_deployment.assert_called_once_with(deployment)
