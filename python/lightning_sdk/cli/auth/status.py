"""Show the saved CLI login."""

from datetime import datetime
from typing import Any, Dict, Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.lightning_cloud import cli_login
from lightning_sdk.lightning_cloud.login import Auth

_NOT_LOGGED_IN = "You are not logged in. Run `lightning login` first."


def _stamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _user(client: Any) -> Dict[str, Optional[str]]:
    try:
        user = client.auth_service_get_user()
    except Exception:
        return {}
    return {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
    }


def _org_names(client: Any) -> Dict[str, str]:
    try:
        orgs = client.organizations_service_list_organizations().organizations or []
    except Exception:
        return {}
    return {org.id: org.name for org in orgs if getattr(org, "id", None)}


def _teamspace_names(client: Any) -> Dict[str, str]:
    try:
        memberships = client.projects_service_list_memberships(filter_by_user_id=True).memberships or []
    except Exception:
        return {}
    return {member.project_id: member.name for member in memberships if getattr(member, "project_id", None)}


def _grant_lines(grant: Dict[str, Any], orgs: Dict[str, str], teamspaces: Dict[str, str]) -> tuple[str, str]:
    scopes = grant.get("orgs")
    if scopes == "all":
        return "all", "all"
    if not isinstance(scopes, list) or not scopes:
        return "none", "none"

    shown_orgs: list[str] = []
    shown_teamspaces: list[str] = []
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        org_id = str(scope.get("org", ""))
        shown_orgs.append(orgs.get(org_id, org_id))
        for project in scope.get("projects") or []:
            project_id = str(project)
            shown_teamspaces.append(teamspaces.get(project_id, project_id))
    return ", ".join(shown_orgs) or "none", ", ".join(shown_teamspaces) or "none"


def _legacy_session() -> bool:
    auth = Auth()
    return bool(auth.load() and auth.auth_token)


@click.command("status", cls=LightningCommand)
def status() -> None:
    """Show who is logged in, the login's reach, its permissions and when it expires."""
    login = cli_login.current_login()
    client = cached_lightning_client()
    user = _user(client)

    if login is None:
        if not _legacy_session():
            raise click.ClickException(_NOT_LOGGED_IN)
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("User", user.get("username") or user.get("email") or user.get("id") or "unknown")
        table.add_row("Login", "session token saved by an older SDK")
        table.add_row("Expiry", "managed by the server")
        table.add_row("Hint", "Run `lightning login` to use the new login.")
        click.echo(rich_to_str(table), color=True)
        return

    if login.grant.get("orgs") == "all":
        orgs, teamspaces = "all", "all"
    else:
        orgs, teamspaces = _grant_lines(login.grant, _org_names(client), _teamspace_names(client))
    permissions = ", ".join(login.grant.get("permissions") or []) or "none"

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("User", user.get("username") or user.get("email") or user.get("id") or "unknown")
    if user.get("email"):
        table.add_row("Email", user["email"])
    if user.get("id"):
        table.add_row("User ID", user["id"])
    table.add_row("Storage", login.storage)
    table.add_row("Orgs", orgs)
    table.add_row("Teamspaces", teamspaces)
    table.add_row("Permissions", permissions)
    table.add_row("Access expires", _stamp(login.access_expires_at))
    table.add_row("Login expires", _stamp(login.refresh_expires_at))
    click.echo(rich_to_str(table), color=True)
