import json
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli


def test_studio_env_list_set_and_delete_resolve_resource():
    teamspace = MagicMock()
    studio = MagicMock()
    studio.env = {"Z_VALUE": "last", "DEBUG": "true"}

    with patch("lightning_sdk.cli.studio.env.resolve_teamspace", return_value=teamspace) as resolve_teamspace, patch(
        "lightning_sdk.cli.studio.env.resolve_studio", return_value=studio
    ) as resolve_studio:
        listed = CliRunner().invoke(
            main_cli, ["studio", "env", "list", "--name", "dev", "--teamspace", "acme/research", "--json"]
        )
        set_result = CliRunner().invoke(
            main_cli, ["studio", "env", "set", "DEBUG=", "--name", "dev", "--teamspace", "acme/research", "--json"]
        )
        deleted = CliRunner().invoke(
            main_cli,
            ["studio", "env", "delete", "DEBUG", "--name", "dev", "--teamspace", "acme/research", "--json"],
        )

    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output) == {
        "environment_variables": [
            {"name": "DEBUG", "value": "true"},
            {"name": "Z_VALUE", "value": "last"},
        ]
    }
    assert json.loads(set_result.output) == {"name": "DEBUG", "status": "set"}
    assert json.loads(deleted.output) == {"name": "DEBUG", "status": "deleted"}
    studio.set_env.assert_called_once_with({"DEBUG": ""})
    studio.delete_env.assert_called_once_with("DEBUG")
    assert resolve_teamspace.call_count == 3
    assert resolve_studio.call_args_list == [call("dev", teamspace), call("dev", teamspace), call("dev", teamspace)]


def test_studio_env_omitted_name_uses_context_and_invalid_assignment_fails_first():
    teamspace = MagicMock()
    studio = MagicMock()
    studio.env = {}

    with patch("lightning_sdk.cli.studio.env.resolve_teamspace", return_value=teamspace), patch(
        "lightning_sdk.cli.studio.env.resolve_studio", return_value=studio
    ) as resolve_studio:
        listed = CliRunner().invoke(main_cli, ["studio", "env", "list", "--json"])
        invalid = CliRunner().invoke(main_cli, ["studio", "env", "set", "INVALID"])

    assert listed.exit_code == 0, listed.output
    resolve_studio.assert_called_once_with(None, teamspace)
    assert invalid.exit_code != 0
    studio.set_env.assert_not_called()
