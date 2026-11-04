import time
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock

from click.testing import CliRunner

from lightning_sdk.cli.entrypoint import main_cli
from lightning_sdk.lightning_cloud.cli_login import LoginError, LoginStatus


def _status(grant=None) -> LoginStatus:
    now = time.time()
    return LoginStatus(
        url="https://platform.lightning.ai",
        storage="keychain",
        access_expires_at=now + 3600,
        refresh_expires_at=now + 90 * 24 * 3600,
        grant=grant or {"orgs": "all", "permissions": ["read", "write"]},
    )


def _client() -> MagicMock:
    client = MagicMock()
    client.auth_service_get_user.return_value = SimpleNamespace(id="user-1", username="ada", email="ada@example.com")
    client.organizations_service_list_organizations.return_value = SimpleNamespace(
        organizations=[SimpleNamespace(id="org-1", name="acme"), SimpleNamespace(id="org-2", name="beta")]
    )
    client.projects_service_list_memberships.return_value = SimpleNamespace(
        memberships=[SimpleNamespace(project_id="proj-1", name="research")]
    )
    return client


def test_auth_status_shows_the_login_without_a_token(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.auth.status.cli_login.current_login", lambda: _status())
    monkeypatch.setattr("lightning_sdk.cli.auth.status.cached_lightning_client", _client)

    result = CliRunner().invoke(main_cli, ["auth", "status"])

    assert result.exit_code == 0, result.output
    assert "ada" in result.output
    assert "ada@example.com" in result.output
    assert "keychain" in result.output
    assert "all" in result.output
    assert "read, write" in result.output
    assert "lit_ua_" not in result.output


def test_auth_status_resolves_a_narrowed_grant(monkeypatch) -> None:
    grant = {"orgs": [{"org": "org-1", "projects": ["proj-1"]}], "permissions": ["read"]}
    monkeypatch.setattr("lightning_sdk.cli.auth.status.cli_login.current_login", lambda: _status(grant))
    monkeypatch.setattr("lightning_sdk.cli.auth.status.cached_lightning_client", _client)

    result = CliRunner().invoke(main_cli, ["auth", "status"])

    assert result.exit_code == 0, result.output
    assert "acme" in result.output
    assert "research" in result.output
    assert "read" in result.output


def test_auth_status_instructs_login_without_a_login(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.auth.status.cli_login.current_login", lambda: None)
    auth = MagicMock()
    auth.load.return_value = False
    monkeypatch.setattr("lightning_sdk.cli.auth.status.Auth", lambda: auth)

    result = CliRunner().invoke(main_cli, ["auth", "status"])

    assert result.exit_code == 1
    assert "Run `lightning login` first" in result.output


def test_auth_token_prints_only_the_token(monkeypatch) -> None:
    monkeypatch.setattr("lightning_sdk.cli.auth.token.cli_login.token", lambda: "lit_ua_access")

    result = CliRunner().invoke(main_cli, ["auth", "token"])

    assert result.exit_code == 0, result.output
    assert result.output == "lit_ua_access\n"


def test_auth_token_falls_back_to_a_saved_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "lightning_sdk.cli.auth.token.cli_login.token",
        MagicMock(side_effect=LoginError("You are not logged in. Run `lightning login`.")),
    )
    auth = MagicMock(auth_header="Bearer sess_saved")
    monkeypatch.setattr("lightning_sdk.cli.auth.token.Auth", lambda: auth)

    result = CliRunner().invoke(main_cli, ["auth", "token"])

    assert result.exit_code == 0, result.output
    assert result.output == "sess_saved\n"


def test_auth_token_reports_a_missing_login(monkeypatch) -> None:
    monkeypatch.setattr(
        "lightning_sdk.cli.auth.token.cli_login.token",
        MagicMock(side_effect=LoginError("You are not logged in. Run `lightning login`.")),
    )
    auth = MagicMock()
    type(auth).auth_header = PropertyMock(side_effect=ValueError("missing"))
    monkeypatch.setattr("lightning_sdk.cli.auth.token.Auth", lambda: auth)

    result = CliRunner().invoke(main_cli, ["auth", "token"])

    assert result.exit_code == 1
    assert "lightning login" in result.output
