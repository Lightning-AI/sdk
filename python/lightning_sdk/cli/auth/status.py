"""Show the credential requests send, and what a saved login reaches."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.lightning_cloud import cli_login, env, service_account
from lightning_sdk.lightning_cloud.credentials import Credential, CredentialKind, CredentialSource

_NOT_LOGGED_IN = "You are not logged in. Run `lightning login`."
_UNKNOWN_REACH = "not known locally"
_UNKNOWN = "not known"
# The members list calls the owner role Admin.
_ROLE_LABELS = {
    "OrganizationOwner": "Admin",
    "OrganizationMember": "Member",
    "ProjectAdministrator": "Administrator",
    "InvokeOnly": "Invoke only",
}


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


def _grant_lines(grant: Dict[str, Any], orgs: Dict[str, str], teamspaces: Dict[str, str]) -> tuple:
    scopes = grant.get("orgs")
    if scopes == "all":
        return "all", "all"
    if not isinstance(scopes, list) or not scopes:
        return "none", "none"

    shown_orgs = []
    shown_teamspaces = []
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        org_id = str(scope.get("org", ""))
        org_name = orgs.get(org_id, org_id)
        shown_orgs.append(org_name)
        projects = scope.get("projects")
        if projects == "all":
            shown_teamspaces.append(f"all in {org_name}")
            continue
        if not isinstance(projects, list):
            continue
        for project in projects:
            project_id = str(project)
            shown_teamspaces.append(teamspaces.get(project_id, project_id))
    return ", ".join(shown_orgs) or "none", ", ".join(shown_teamspaces) or "none"


def _source(credential: Credential) -> str:
    if credential.kind is CredentialKind.TOKEN_FILE:
        return f"token file {os.environ.get(env.LIGHTNING_AUTH_TOKEN_FILE, '')}"
    if credential.kind is CredentialKind.ENV_TOKEN:
        return "LIGHTNING_AUTH_TOKEN"
    if credential.kind is CredentialKind.SERVICE_ACCOUNT:
        return "service-account key in LIGHTNING_API_KEY"
    if credential.kind is CredentialKind.LOGIN:
        login = cli_login.current_login()
        storage = login.storage if login is not None else "login"
        return f"login ({storage})"
    return "interim session login"


def _role_names(roles: Any) -> str:
    names = [_ROLE_LABELS.get(role.name, role.name) for role in roles or [] if getattr(role, "name", None)]
    return ", ".join(names) or "none"


def _org_role(client: Any, org_id: str, account_id: str) -> str:
    try:
        roles = client.organizations_service_list_org_roles(org_id=org_id, user_id=account_id).roles
    except Exception:
        return _UNKNOWN
    return _role_names(roles)


def _account_teamspaces(client: Any) -> str:
    try:
        memberships = client.projects_service_list_memberships(filter_by_user_id=True).memberships or []
    except Exception:
        return _UNKNOWN
    shown = [
        f"{m.name or m.project_id} ({_role_names(m.roles)})" for m in memberships if getattr(m, "project_id", None)
    ]
    return ", ".join(shown) or "none"


def _add_service_account(table: Table, client: Any, user: Dict[str, Optional[str]]) -> None:
    """Who a key acts as, and what it reaches: its org always, its roles from its memberships."""
    try:
        details = service_account.details()
    except cli_login.LoginError as err:
        raise click.ClickException(str(err)) from err
    if details is None or details.account_id is None:
        # A server that doesn't name the account in the exchange.
        _add_user(table, user)
    else:
        name = details.account_name or "unnamed"
        table.add_row("Service account", f"{name} ({details.account_id})")
    table.add_row("Source", "service-account key in LIGHTNING_API_KEY")
    if details is None:
        return
    org_id = details.org_id
    if org_id is None:
        table.add_row("Org", _UNKNOWN)
    else:
        table.add_row("Org", f"{details.org_name} ({org_id})" if details.org_name else org_id)
        if details.account_id is not None:
            table.add_row("Org role", _org_role(client, org_id, details.account_id))
    table.add_row("Teamspaces", _account_teamspaces(client))
    table.add_row("Permissions", ", ".join(details.permissions) or "none")
    table.add_row("Access expires", _stamp(details.access_expires_at))
    table.add_row("Key expires", _stamp(details.key_expires_at) if details.key_expires_at is not None else _UNKNOWN)


def _add_user(table: Table, user: Dict[str, Optional[str]]) -> None:
    table.add_row("User", user.get("username") or user.get("email") or user.get("id") or "unknown")
    if user.get("email"):
        table.add_row("Email", user["email"])
    if user.get("id"):
        table.add_row("User ID", user["id"])


@click.command("status", cls=LightningCommand)
def status() -> None:
    """Show the credential requests send, who it belongs to, and what a saved login reaches."""
    try:
        credential = CredentialSource().resolve()
    except (OSError, cli_login.LoginError) as err:
        raise click.ClickException(str(err)) from err
    if credential is None:
        raise click.ClickException(_NOT_LOGGED_IN)

    client = cached_lightning_client()
    user = _user(client)
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    if credential.kind is CredentialKind.SERVICE_ACCOUNT:
        _add_service_account(table, client, user)
        click.echo(rich_to_str(table), color=True)
        return
    _add_user(table, user)
    table.add_row("Source", _source(credential))

    login = cli_login.current_login() if credential.kind is CredentialKind.LOGIN else None
    if login is None:
        table.add_row("Orgs", _UNKNOWN_REACH)
        table.add_row("Teamspaces", _UNKNOWN_REACH)
        table.add_row("Permissions", _UNKNOWN_REACH)
        table.add_row("Expiry", _UNKNOWN_REACH)
    else:
        orgs, teamspaces = _grant_lines(login.grant, _org_names(client), _teamspace_names(client))
        permissions = ", ".join(login.grant.get("permissions") or []) or "none"
        table.add_row("Orgs", orgs)
        table.add_row("Teamspaces", teamspaces)
        table.add_row("Permissions", permissions)
        table.add_row("Access expires", _stamp(login.access_expires_at))
        table.add_row("Login expires", _stamp(login.refresh_expires_at))
    click.echo(rich_to_str(table), color=True)
