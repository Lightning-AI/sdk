import json
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner

from lightning_sdk.api.deployment_api import Env, Secret
from lightning_sdk.cli.entrypoint import main_cli


def test_deployment_secret_list_renders_only_references_with_injected_names():
    teamspace = MagicMock()
    deployment = MagicMock()
    deployment.env = [Secret("SERVICE_A_GCP", env_name="GCP_JSON"), Env("DEBUG", "true"), Secret("TOKEN")]

    with patch("lightning_sdk.cli.deployment.secret.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.deployment.secret.resolve_deployment", return_value=deployment
    ) as resolve_deployment:
        result = CliRunner().invoke(
            main_cli,
            ["deployment", "secret", "list", "--name", "serve", "--teamspace", "acme/research", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "secrets": [
            {"from_secret": "SERVICE_A_GCP", "name": "GCP_JSON"},
            {"from_secret": "TOKEN", "name": "TOKEN"},
        ]
    }
    resolve_deployment.assert_called_once_with("serve", teamspace)


def test_deployment_secret_set_and_delete_delegate_to_resource():
    teamspace = MagicMock()
    deployment = MagicMock()

    with patch("lightning_sdk.cli.deployment.secret.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.deployment.secret.resolve_deployment", return_value=deployment
    ) as resolve_deployment:
        plain = CliRunner().invoke(
            main_cli,
            ["deployment", "secret", "set", "TOKEN", "--name", "serve", "--teamspace", "acme/research", "--json"],
        )
        aliased = CliRunner().invoke(
            main_cli,
            [
                "deployment",
                "secret",
                "set",
                "GCP_JSON=SERVICE_A_GCP",
                "--name",
                "serve",
                "--teamspace",
                "acme/research",
                "--json",
            ],
        )
        delete_result = CliRunner().invoke(
            main_cli,
            ["deployment", "secret", "delete", "GCP_JSON", "--name", "serve", "--teamspace", "acme/research", "--json"],
        )

    assert plain.exit_code == 0, plain.output
    assert aliased.exit_code == 0, aliased.output
    assert delete_result.exit_code == 0, delete_result.output
    assert deployment.set_secret.call_args_list == [
        call("TOKEN", None),
        call("SERVICE_A_GCP", "GCP_JSON"),
    ]
    deployment.delete_secret.assert_called_once_with("GCP_JSON")
    assert resolve_deployment.call_args_list == [call("serve", teamspace)] * 3


def test_deployment_secret_requires_name_and_offers_json():
    missing = CliRunner().invoke(main_cli, ["deployment", "secret", "list"])

    assert missing.exit_code != 0
    assert "--name" in missing.output
    assert "--json" in CliRunner().invoke(main_cli, ["deployment", "secret", "list", "--help"]).output
