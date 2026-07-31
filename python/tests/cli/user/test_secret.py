import json
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli


def test_user_secret_list_json_is_sorted_and_redacted():
    user = MagicMock()
    user.secrets = {"Z_TOKEN": "sdk-secret-canary-7f3a", "A_TOKEN": "encrypted"}

    with patch("lightning_sdk.cli.user.secret._get_authed_user", return_value=user):
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
    user = MagicMock()

    with patch("lightning_sdk.cli.user.secret._get_authed_user", return_value=user):
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
    assert user.set_secret.call_args_list == [call("TOKEN", canary), call("OTHER_TOKEN", canary)]
    assert '"status": "set"' in prompt_result.output


def test_user_secret_delete_and_invalid_inputs():
    user = MagicMock()
    with patch("lightning_sdk.cli.user.secret._get_authed_user", return_value=user):
        deleted = CliRunner().invoke(main_cli, ["user", "secret", "delete", "TOKEN", "--json"])
        invalid_name = CliRunner().invoke(main_cli, ["user", "secret", "delete", "BAD-NAME"])
        value_option = CliRunner().invoke(
            main_cli, ["user", "secret", "set", "TOKEN", "--value", "sdk-secret-canary-7f3a"]
        )

    assert deleted.exit_code == 0, deleted.output
    assert json.loads(deleted.output) == {"name": "TOKEN", "status": "deleted"}
    user.delete_secret.assert_called_once_with("TOKEN")
    assert invalid_name.exit_code != 0
    assert value_option.exit_code != 0
    assert "sdk-secret-canary-7f3a" not in value_option.output
