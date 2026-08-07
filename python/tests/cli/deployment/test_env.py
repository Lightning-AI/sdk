import json
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner

from lightning_sdk.api.deployment_api import Env, Secret
from lightning_sdk.cli.entrypoint import main_cli


def test_deployment_env_list_renders_literals_and_secret_references():
    teamspace = MagicMock()
    deployment = MagicMock()
    deployment.env = [Secret("TOKEN"), Env("DEBUG", "true")]

    with patch("lightning_sdk.cli.deployment.env.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.deployment.env.resolve_deployment", return_value=deployment
    ) as resolve_deployment:
        result = CliRunner().invoke(
            main_cli,
            ["deployment", "env", "list", "--name", "serve", "--teamspace", "acme/research", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "environment_variables": [
            {"name": "DEBUG", "value": "true"},
            {"from_secret": "TOKEN", "name": "TOKEN"},
        ]
    }
    resolve_deployment.assert_called_once_with("serve", teamspace)


def test_deployment_env_set_and_delete_delegate_to_resource():
    teamspace = MagicMock()
    deployment = MagicMock()

    with patch("lightning_sdk.cli.deployment.env.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.deployment.env.resolve_deployment", return_value=deployment
    ) as resolve_deployment:
        set_result = CliRunner().invoke(
            main_cli,
            ["deployment", "env", "set", "DEBUG=", "--name", "serve", "--teamspace", "acme/research", "--json"],
        )
        delete_result = CliRunner().invoke(
            main_cli,
            ["deployment", "env", "delete", "DEBUG", "--name", "serve", "--teamspace", "acme/research", "--json"],
        )

    assert set_result.exit_code == 0, set_result.output
    assert delete_result.exit_code == 0, delete_result.output
    deployment.set_env.assert_called_once_with({"DEBUG": ""})
    deployment.delete_env.assert_called_once_with("DEBUG")
    assert resolve_deployment.call_args_list == [call("serve", teamspace), call("serve", teamspace)]


def test_deployment_env_requires_name_and_all_lists_offer_json():
    missing = CliRunner().invoke(main_cli, ["deployment", "env", "list"])

    assert missing.exit_code != 0
    assert "--name" in missing.output
    assert "--json" in CliRunner().invoke(main_cli, ["deployment", "env", "list", "--help"]).output
    assert "--json" in CliRunner().invoke(main_cli, ["studio", "env", "list", "--help"]).output
