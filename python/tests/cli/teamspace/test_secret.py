import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli


def test_teamspace_secret_commands_resolve_slug_and_redact_lists():
    teamspace = MagicMock()
    teamspace.secrets = {"TOKEN": "sdk-secret-canary-7f3a"}

    with patch("lightning_sdk.cli.teamspace.secret.resolve_teamspace", return_value=teamspace) as resolve:
        listed = CliRunner().invoke(main_cli, ["teamspace", "secret", "list", "--teamspace", "acme/research", "--json"])
        deleted = CliRunner().invoke(
            main_cli, ["teamspace", "secret", "delete", "TOKEN", "--teamspace", "acme/research", "--json"]
        )

    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output) == {"secrets": [{"name": "TOKEN", "value": "***REDACTED***"}]}
    assert "sdk-secret-canary-7f3a" not in listed.output
    assert json.loads(deleted.output) == {"name": "TOKEN", "status": "deleted"}
    teamspace.delete_secret.assert_called_once_with("TOKEN")
    assert resolve.call_count == 2
    resolve.assert_called_with(teamspace="acme/research", org=None, user=None)


def test_teamspace_secret_set_reads_stdin_and_never_exposes_value():
    canary = "sdk-secret-canary-7f3a"
    teamspace = MagicMock()

    with patch("lightning_sdk.cli.teamspace.secret.resolve_teamspace", return_value=teamspace):
        result = CliRunner().invoke(
            main_cli,
            ["teamspace", "secret", "set", "TOKEN", "--teamspace", "acme/research", "--value-stdin", "--json"],
            input=canary + "\n",
        )

    assert result.exit_code == 0, result.output
    assert canary not in result.output
    teamspace.set_secret.assert_called_once_with("TOKEN", canary)
    assert json.loads(result.output) == {"name": "TOKEN", "status": "set"}


def test_secret_resource_groups_are_registered():
    assert "user" in main_cli.commands
    assert "teamspace" in main_cli.commands
    assert "secret" in main_cli.commands["user"].commands
    assert "secret" in main_cli.commands["teamspace"].commands
    for resource in ("user", "teamspace"):
        assert set(main_cli.commands[resource].commands["secret"].commands) == {"list", "set", "delete"}
