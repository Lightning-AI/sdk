"""Show the credential requests send, who it acts as, and what it reaches."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import rich_click as click
from rich.table import Table

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.credentials import Credential, CredentialKind, CredentialSource

_NOT_LOGGED_IN = "You are not logged in. Run `lightning login`."
_UNKNOWN = "not known"
# The members list calls the owner role Admin.
_ROLE_LABELS = {
    "OrganizationOwner": "Admin",
    "OrganizationMember": "Member",
    "ProjectAdministrator": "Administrator",
    "InvokeOnly": "Invoke only",
}
_WORKLOAD_LABELS = {"cloudSpaceInstance": "Studio", "job": "Job", "sandbox": "Sandbox"}


def _stamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _timestamp(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _whoami(client: Any) -> Dict[str, Any]:
    """The server's description of the credential. Read raw, so fields newer than this client still arrive."""
    try:
        response = client.auth_service_whoami(_preload_content=False)
        body = json.loads(response.data)
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


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


def _login_grant(client: Any, grant: Dict[str, Any]) -> Dict[str, Any]:
    """A saved login's grant in whoami's shape, named from the caller's orgs and teamspaces."""
    scopes = grant.get("orgs")
    described: Dict[str, Any] = {"allOrgs": scopes == "all", "orgs": [], "permissions": grant.get("permissions")}
    if not isinstance(scopes, list):
        return described
    orgs = _org_names(client)
    teamspaces = _teamspace_names(client)
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        org_id = str(scope.get("org", ""))
        projects = scope.get("projects")
        described["orgs"].append(
            {
                "orgId": org_id,
                "orgName": orgs.get(org_id),
                "allProjects": projects == "all",
                "projects": [
                    {"id": str(p), "name": teamspaces.get(str(p))}
                    for p in (projects if isinstance(projects, list) else [])
                ],
            }
        )
    return described


def _grant_lines(grant: Dict[str, Any]) -> Tuple[str, str]:
    if grant.get("allOrgs"):
        return "all", "all"
    shown_orgs: List[str] = []
    shown_teamspaces: List[str] = []
    for scope in grant.get("orgs") or []:
        if not isinstance(scope, dict):
            continue
        org_name = scope.get("orgName") or scope.get("orgId") or "unknown"
        shown_orgs.append(org_name)
        if scope.get("allProjects"):
            shown_teamspaces.append(f"all in {org_name}")
            continue
        for project in scope.get("projects") or []:
            if isinstance(project, dict):
                shown_teamspaces.append(project.get("name") or project.get("id") or "unknown")
    return ", ".join(shown_orgs) or "none", ", ".join(shown_teamspaces) or "none"


def _permissions(grant: Dict[str, Any]) -> str:
    permissions = grant.get("permissions")
    return ", ".join(p for p in permissions if isinstance(p, str)) if isinstance(permissions, list) else "none"


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


def _add_identity(table: Table, client: Any, me: Dict[str, Any]) -> None:
    account = me.get("serviceAccount")
    if isinstance(account, dict) and account.get("id"):
        table.add_row("Service account", f"{account.get('name') or 'unnamed'} ({account['id']})")
        return
    if not me:
        try:
            user = client.auth_service_get_user()
            me = {"userId": user.id, "username": user.username, "email": user.email}
        except Exception:
            me = {}
    table.add_row("User", me.get("username") or me.get("email") or me.get("userId") or "unknown")
    if me.get("email"):
        table.add_row("Email", me["email"])
    if me.get("userId"):
        table.add_row("User ID", me["userId"])


def _add_service_account(table: Table, client: Any, account: Dict[str, Any], me: Dict[str, Any]) -> None:
    """An account's org always, and what it reaches through its roles, which its grant doesn't narrow."""
    org_id = account.get("orgId")
    if not org_id:
        table.add_row("Org", _UNKNOWN)
    else:
        table.add_row("Org", f"{account['orgName']} ({org_id})" if account.get("orgName") else org_id)
        table.add_row("Org role", _org_role(client, org_id, account["id"]))
    table.add_row("Teamspaces", _account_teamspaces(client))
    table.add_row("Permissions", _permissions(me))
    _add_expiry(table, "Access expires", me.get("expiresAt"))
    _add_expiry(table, "Key expires", me.get("keyExpiresAt"))


def _add_expiry(table: Table, label: str, value: Any) -> None:
    at = _timestamp(value)
    table.add_row(label, _stamp(at) if at is not None else _UNKNOWN)


@click.command("status", cls=LightningCommand)
def status() -> None:
    """Show the credential requests send, who it acts as, and what it reaches."""
    try:
        credential = CredentialSource().resolve()
    except (OSError, cli_login.LoginError) as err:
        raise click.ClickException(str(err)) from err
    if credential is None:
        raise click.ClickException(_NOT_LOGGED_IN)

    client = cached_lightning_client()
    me = _whoami(client)
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    _add_identity(table, client, me)
    table.add_row("Source", _source(credential))

    account = me.get("serviceAccount")
    login = cli_login.current_login() if credential.kind is CredentialKind.LOGIN else None
    if isinstance(account, dict) and account.get("id"):
        _add_service_account(table, client, account, me)
    elif me.get("credentialKind") or login is not None:
        # A server that doesn't describe the credential still leaves a saved login's own grant.
        grant = me if me.get("credentialKind") else _login_grant(client, login.grant)
        orgs, teamspaces = _grant_lines(grant)
        table.add_row("Orgs", orgs)
        table.add_row("Teamspaces", teamspaces)
        table.add_row("Permissions", _permissions(grant))
        workload = me.get("workload")
        if isinstance(workload, dict) and workload.get("resourceId"):
            kind = workload.get("resourceType", "")
            table.add_row("Workload", f"{_WORKLOAD_LABELS.get(kind, kind)} {workload['resourceId']}".strip())
        if me.get("credentialKind"):
            _add_expiry(table, "Access expires", me.get("expiresAt"))
        elif login is not None:
            table.add_row("Access expires", _stamp(login.access_expires_at))
        if login is not None:
            table.add_row("Login expires", _stamp(login.refresh_expires_at))
    else:
        for field in ("Orgs", "Teamspaces", "Permissions", "Expires"):
            table.add_row(field, _UNKNOWN)
    click.echo(rich_to_str(table), color=True)
