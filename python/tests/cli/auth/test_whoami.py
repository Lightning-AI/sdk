import json
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from lightning_sdk.cli.auth.whoami import whoami
from lightning_sdk.lightning_cloud.openapi import V1AuthType
from tests.cli.help import assert_help_contains, mock_command_logging


def _identity(**overrides: object) -> SimpleNamespace:
    base = {
        "auth_type": V1AuthType.USER,
        "user_id": "u-1",
        "username": "alice",
        "email": "alice@example.ai",
        "org_id": None,
        "project_id": None,
        "role_id": None,
        "api_key_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@mock_command_logging
def test_auth_whoami_help() -> None:
    assert_help_contains(
        "lightning auth whoami --help",
        "Usage: lightning auth whoami",
        "Show who you are authenticated as.",
        "--json",
    )


@mock_command_logging
def test_whoami_user_hides_scoped_fields() -> None:
    with patch("lightning_sdk.cli.auth.whoami.AuthApi") as api_cls:
        api_cls.return_value.whoami.return_value = _identity()
        result = CliRunner().invoke(whoami, [])

    assert result.exit_code == 0, result.output
    assert "user" in result.output
    assert "alice" in result.output
    # A personal key has no org/project/role binding, so those rows are omitted.
    assert "Org ID" not in result.output
    assert "Role ID" not in result.output


@mock_command_logging
def test_whoami_scoped_key_shows_binding() -> None:
    with patch("lightning_sdk.cli.auth.whoami.AuthApi") as api_cls:
        api_cls.return_value.whoami.return_value = _identity(
            auth_type=V1AuthType.SCOPED_API_KEY,
            org_id="org-1",
            project_id="proj-1",
            role_id="role-1",
            api_key_id="key-1",
        )
        result = CliRunner().invoke(whoami, [])

    assert result.exit_code == 0, result.output
    assert "scoped-api-key" in result.output
    assert "org-1" in result.output
    assert "role-1" in result.output


@mock_command_logging
def test_whoami_json() -> None:
    with patch("lightning_sdk.cli.auth.whoami.AuthApi") as api_cls:
        api_cls.return_value.whoami.return_value = _identity(
            auth_type=V1AuthType.SCOPED_API_KEY,
            org_id="org-1",
            role_id="role-1",
        )
        result = CliRunner().invoke(whoami, ["--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["auth_type"] == "scoped-api-key"
    assert data["user_id"] == "u-1"
    assert data["org_id"] == "org-1"
    assert data["role_id"] == "role-1"
    assert data["project_id"] is None
