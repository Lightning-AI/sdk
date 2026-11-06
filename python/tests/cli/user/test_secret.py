import json
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli

_USER_API = "lightning_sdk.cli.user.secret.UserApi"


def test_user_secret_list_json_is_sorted_and_redacted():
    user_api = MagicMock()
    user_api.get_secrets.return_value = {"Z_TOKEN": "sdk-secret-canary-7f3a", "A_TOKEN": "encrypted"}

    with patch(_USER_API, return_value=user_api):
        result = CliRunner().invoke(main_cli, ["user", "secret", "list", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "secrets": [
            {"name": "A_TOKEN", "value": "***REDACTED***"},
            {"name": "Z_TOKEN", "value": "***REDACTED***"},
        ]
    }
    assert "sdk-secret-canary-7f3a" not in result.output


def test_user_secret_set_supports_hidden_prompt_and_stdin_without_leaking():
    canary = "sdk-secret-canary-7f3a"
    user_api = MagicMock()

    with patch(_USER_API, return_value=user_api):
        prompt_result = CliRunner().invoke(main_cli, ["user", "secret", "set", "TOKEN", "--json"], input=canary + "\n")
        stdin_result = CliRunner().invoke(
            main_cli,
            ["user", "secret", "set", "OTHER_TOKEN", "--value-stdin", "--json"],
            input=canary + "\n",
        )

    assert prompt_result.exit_code == 0, prompt_result.output
    assert stdin_result.exit_code == 0, stdin_result.output
    assert canary not in prompt_result.output
    assert canary not in stdin_result.output
    assert user_api.set_secret.call_args_list == [call("TOKEN", canary), call("OTHER_TOKEN", canary)]
    assert '"status": "set"' in prompt_result.output


def test_user_secret_delete_and_invalid_inputs():
    user_api = MagicMock()
    with patch(_USER_API, return_value=user_api):
        deleted = CliRunner().invoke(main_cli, ["user", "secret", "delete", "TOKEN", "--json"])
        invalid_name = CliRunner().invoke(main_cli, ["user", "secret", "delete", "BAD-NAME"])
        value_option = CliRunner().invoke(
            main_cli, ["user", "secret", "set", "TOKEN", "--value", "sdk-secret-canary-7f3a"]
        )

    assert deleted.exit_code == 0, deleted.output
    assert json.loads(deleted.output) == {"name": "TOKEN", "status": "deleted"}
    user_api.delete_secret.assert_called_once_with("TOKEN")
    assert invalid_name.exit_code != 0
    assert value_option.exit_code != 0
    assert "sdk-secret-canary-7f3a" not in value_option.output


def test_user_secret_commands_do_not_call_whoami():
    user_api = MagicMock()
    user_api.get_secrets.return_value = {}

    with patch(_USER_API, return_value=user_api), patch(
        "lightning_sdk.api.auth_api.AuthApi.whoami", side_effect=AssertionError("called whoami")
    ) as whoami:
        listed = CliRunner().invoke(main_cli, ["user", "secret", "list"])
        set_ = CliRunner().invoke(main_cli, ["user", "secret", "set", "TOKEN", "--value-stdin"], input="v")
        deleted = CliRunner().invoke(main_cli, ["user", "secret", "delete", "TOKEN"])

    assert listed.exit_code == 0, listed.output
    assert set_.exit_code == 0, set_.output
    assert deleted.exit_code == 0, deleted.output
    assert whoami.call_count == 0
