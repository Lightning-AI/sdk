import json
from unittest.mock import patch

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli

_TEAMSPACES = {"acme": {"research": "ts-2", "apps": "ts-1"}, "alice": {}}


def test_teamspace_list_json_is_sorted_and_skips_empty_owners():
    with patch("lightning_sdk.cli.teamspace.list.accessible_teamspaces", return_value=_TEAMSPACES):
        result = CliRunner().invoke(main_cli, ["teamspace", "list", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "teamspaces": [
            {"owner": "acme", "name": "apps"},
            {"owner": "acme", "name": "research"},
        ]
    }


def test_teamspace_list_table_and_plural_alias():
    with patch("lightning_sdk.cli.teamspace.list.accessible_teamspaces", return_value=_TEAMSPACES):
        result = CliRunner().invoke(main_cli, ["teamspaces", "list"])

    assert result.exit_code == 0, result.output
    assert "acme/apps" in result.output
    assert "acme/research" in result.output
