"""CLI authentication commands, on top of the vendored credential source."""

import json
import os
from typing import Any, Dict, Optional, Sequence

import click

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.credentials import (
    CredentialKind,
    CredentialSource,
    LoginUnavailable,
    logout,
    start_login,
)
from lightning_sdk.lightning_cloud.credentials import browser_login as browser_authentication
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.resolve import _get_authed_user, in_studio

__all__ = ["browser_authentication", "require_auth_header", "run_login", "run_logout"]

_REVOKE_FAILED = {
    CredentialKind.LOGIN: ("The saved login could not be revoked on the server and may work until it expires."),
    CredentialKind.SESSION: ("The saved session could not be revoked on the server and may work until it expires."),
}


def require_auth_header() -> str:
    """The credential requests send, or a usage error that tells the user to log in."""
    try:
        header = Auth().auth_header
    except (ValueError, ConnectionError) as err:
        raise click.UsageError(str(err)) from err
    if not header:
        raise click.UsageError("No Lightning credentials are available. Run `lightning login` first.")
    return header


def _env_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _org_list(orgs: Optional[str]) -> Optional[Sequence[str]]:
    if not orgs:
        return None
    names = [part.strip() for part in orgs.split(",") if part.strip()]
    return names or None


def _grant_reaches_further(grant: Dict[str, Any], orgs: Optional[Sequence[str]], project: Optional[str]) -> bool:
    """Whether ``grant`` covers more than the orgs and project the user asked for."""
    scopes = grant.get("orgs")
    asked = {org for org in orgs or [] if org}
    if scopes == "all":
        return bool(asked or project)
    if not isinstance(scopes, list):
        return False
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        org = str(scope.get("org", ""))
        projects = scope.get("projects")
        if asked and org not in asked:
            return True
        if not project:
            continue
        if not isinstance(projects, list) or not projects:
            return True
        named = [str(item) for item in projects]
        if project not in named or len(named) > 1:
            return True
    return False


def run_login(
    no_browser: bool = False,
    insecure_storage: bool = False,
    orgs: Optional[str] = None,
    project: Optional[str] = None,
) -> None:
    """Run the login the switch selects, without dropping the saved login first."""
    if _env_set(env.LIGHTNING_AUTH_TOKEN_FILE):
        raise click.UsageError(
            "LIGHTNING_AUTH_TOKEN_FILE is set, so a new login would not be what requests send. "
            "Unset it and run `lightning login` again."
        )
    if _env_set("LIGHTNING_AUTH_TOKEN"):
        raise click.UsageError(
            "LIGHTNING_AUTH_TOKEN is set, so a new login would not be what requests send. "
            "Unset it and run `lightning login` again."
        )
    if _env_set("LIGHTNING_API_KEY"):
        if not cli_login.oidc_login_enabled():
            # A saved login outranks the key, so a stale one can only be replaced by logging in.
            sent = CredentialSource().resolve()
            if sent is not None and sent.kind is CredentialKind.LEGACY_KEY:
                click.echo(
                    '"lightning login" is not required within a Studio or when credentials are set in the environment'
                )
                return
        else:
            click.echo(
                "LIGHTNING_API_KEY is ignored until service accounts. This login continues without it.",
                err=True,
            )
    if in_studio():
        raise RuntimeError("Unable to login within a Studio. Did you change your shell setup?") from None

    asked_orgs = _org_list(orgs)
    asked_project = project.strip() if isinstance(project, str) and project.strip() else None
    if insecure_storage and cli_login.oidc_login_enabled():
        click.echo(f"This login is kept in a file at {env.LIGHTNING_LOGIN_PATH}.", err=True)
    try:
        done = start_login(
            no_browser=no_browser,
            insecure_storage=insecure_storage,
            orgs=asked_orgs,
            project=asked_project,
        )
    except LoginUnavailable as err:
        raise click.UsageError(str(err)) from err

    wider = done is not None and (asked_orgs or asked_project)
    if wider and _grant_reaches_further(done.grant, asked_orgs, asked_project):
        grant = json.dumps(done.grant, sort_keys=True)
        click.echo(f"This login reaches more than you asked for. The grant is {grant}.")
    try:
        click.echo(f'Successfully logged in as "{_get_authed_user().name}".')
    except Exception:
        click.echo("Successfully logged in.")


def run_logout() -> None:
    """Forget every saved login on this machine, and say which server revoke failed."""
    failed = logout()
    click.echo("Logged out on this machine.")
    for kind in failed:
        click.echo(
            _REVOKE_FAILED.get(
                kind,
                f"The {kind.value} credential could not be revoked on the server and may work until it expires.",
            )
        )
