from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from lightning_sdk.cli.api_key.create import create_api_key
from lightning_sdk.cli.api_key.delete import delete_api_key
from lightning_sdk.cli.api_key.get import get_api_key
from lightning_sdk.cli.api_key.list import list_api_keys
from tests.cli.help import assert_help_contains


def _mock_org(name: str = "test-org", org_id: str = "org-1") -> MagicMock:
    org = MagicMock()
    org.name = name
    org.id = org_id
    return org


def test_api_key_help() -> None:
    assert_help_contains(
        "lightning api-key --help",
        "Usage: lightning api-key",
        "Manage API keys for public model endpoints.",
    )


def test_api_key_get_help() -> None:
    assert_help_contains(
        "lightning api-key get --help",
        "Usage: lightning api-key get",
        "Get a model API key for calling public inference endpoints.",
    )


def test_api_key_create_help() -> None:
    assert_help_contains(
        "lightning api-key create --help",
        "Usage: lightning api-key create",
        "Create an org-scoped API key for model API access.",
    )


def test_api_key_list_help() -> None:
    assert_help_contains(
        "lightning api-key list --help",
        "Usage: lightning api-key list",
        "List org-scoped API keys.",
    )


def test_api_key_delete_help() -> None:
    assert_help_contains(
        "lightning api-key delete --help",
        "Usage: lightning api-key delete",
        "Delete an org-scoped API key.",
    )


def test_get_cli_prints_key() -> None:
    runner = CliRunner()
    with patch("lightning_sdk.cli.api_key.get.ApiKeyApi") as api_cls:
        api_cls.return_value.get_or_create_default.return_value = "cli-key"
        result = runner.invoke(get_api_key, [])

    assert result.exit_code == 0
    assert result.output.strip() == "cli-key"
    api_cls.return_value.get_or_create_default.assert_called_once_with(None)


def test_get_cli_passes_org() -> None:
    runner = CliRunner()
    with patch("lightning_sdk.cli.api_key.get.ApiKeyApi") as api_cls:
        api_cls.return_value.get_or_create_default.return_value = "cli-key"
        result = runner.invoke(get_api_key, ["--org", "my-org"])

    assert result.exit_code == 0
    api_cls.return_value.get_or_create_default.assert_called_once_with("my-org")


def test_create_cli_prints_key() -> None:
    runner = CliRunner()
    org = _mock_org()
    created = MagicMock(raw_key="sk-lit-new")

    with (
        patch("lightning_sdk.cli.api_key.create.resolve_org", return_value=org),
        patch("lightning_sdk.cli.api_key.create.ApiKeyApi") as api_cls,
    ):
        api_cls.return_value.create.return_value = created
        result = runner.invoke(
            create_api_key,
            ["--name", "Demo key", "--description", "Created from CLI demo"],
        )

    assert result.exit_code == 0
    assert result.output.strip() == "sk-lit-new"
    api_cls.return_value.create.assert_called_once_with(
        "org-1",
        "Demo key",
        role_id=None,
        description="Created from CLI demo",
    )


def test_create_cli_errors_when_no_secret() -> None:
    runner = CliRunner()
    org = _mock_org()

    with (
        patch("lightning_sdk.cli.api_key.create.resolve_org", return_value=org),
        patch("lightning_sdk.cli.api_key.create.ApiKeyApi") as api_cls,
    ):
        api_cls.return_value.create.return_value = MagicMock(raw_key=None)
        result = runner.invoke(create_api_key, [])

    assert result.exit_code != 0
    assert "API key was created but no secret was returned." in result.output


def test_create_cli_usage_error_when_org_unresolved() -> None:
    runner = CliRunner()

    with patch(
        "lightning_sdk.cli.api_key.create.resolve_org",
        side_effect=click.UsageError("Could not determine an organization for this account."),
    ):
        result = runner.invoke(create_api_key, [])

    assert result.exit_code != 0
    assert "Could not determine an organization for this account." in result.output


def test_list_cli_shows_keys() -> None:
    runner = CliRunner()
    org = _mock_org()
    key = SimpleNamespace(
        id="key-1",
        name="Default",
        description="demo key",
        created_at=datetime(2026, 6, 1, 22, 29, 55, tzinfo=timezone.utc),
        raw_key="sk-lit-existing",
    )

    with (
        patch("lightning_sdk.cli.api_key.list.resolve_org", return_value=org),
        patch("lightning_sdk.cli.api_key.list.ApiKeyApi") as api_cls,
    ):
        api_cls.return_value.list.return_value = [key]
        result = runner.invoke(list_api_keys, [])

    assert result.exit_code == 0
    assert "API keys for test-org" in result.output
    assert "key-1" in result.output
    assert "Default" in result.output
    assert "demo key" in result.output
    assert "yes" in result.output
    api_cls.return_value.list.assert_called_once_with("org-1", mine_only=True)


def test_list_cli_all_users() -> None:
    runner = CliRunner()
    org = _mock_org()

    with (
        patch("lightning_sdk.cli.api_key.list.resolve_org", return_value=org),
        patch("lightning_sdk.cli.api_key.list.ApiKeyApi") as api_cls,
    ):
        api_cls.return_value.list.return_value = []
        result = runner.invoke(list_api_keys, ["--all-users"])

    assert result.exit_code == 0
    api_cls.return_value.list.assert_called_once_with("org-1", mine_only=False)


def test_delete_cli_prints_confirmation() -> None:
    runner = CliRunner()
    org = _mock_org()

    with (
        patch("lightning_sdk.cli.api_key.delete.resolve_org", return_value=org),
        patch("lightning_sdk.cli.api_key.delete.ApiKeyApi") as api_cls,
    ):
        result = runner.invoke(delete_api_key, ["key-123"])

    assert result.exit_code == 0
    assert result.output.strip() == "Deleted API key key-123."
    api_cls.return_value.delete.assert_called_once_with("org-1", "key-123")
