"""CLI authentication commands, on top of the vendored credential source."""

import os

import click

from lightning_sdk.lightning_cloud import cli_login, env
from lightning_sdk.lightning_cloud.credentials import (
    REVOKE_FAILED,
    LoginUnavailable,
    logout,
    start_login,
)
from lightning_sdk.lightning_cloud.credentials import browser_login as browser_authentication
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.resolve import _get_authed_user, in_studio

__all__ = ["browser_authentication", "require_auth_header", "run_login", "run_logout"]


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


def run_login(
    no_browser: bool = False,
    no_keychain: bool = False,
) -> None:
    """Run the login the switch selects, without dropping the saved login first."""
    if in_studio():
        raise RuntimeError("Unable to login within a Studio. Did you change your shell setup?") from None

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
        click.echo(
            "LIGHTNING_API_KEY is ignored until service accounts. This login continues without it.",
            err=True,
        )

    if no_keychain and cli_login.oidc_login_enabled():
        click.echo(f"This login is kept in a file at {env.LIGHTNING_LOGIN_PATH}.", err=True)
    try:
        start_login(
            no_browser=no_browser,
            no_keychain=no_keychain,
        )
    except LoginUnavailable as err:
        raise click.UsageError(str(err)) from err

    try:
        click.echo(f'Successfully logged in as "{_get_authed_user().name}".')
    except Exception:
        click.echo("Successfully logged in.")


def run_logout() -> None:
    """Forget every saved login on this machine, and say which server revoke failed."""
    failed = logout()
    click.echo("Logged out on this machine.")
    for kind in failed:
        click.echo(REVOKE_FAILED[kind])
    for name in (env.LIGHTNING_AUTH_TOKEN_FILE, "LIGHTNING_AUTH_TOKEN"):
        if _env_set(name):
            click.echo(f"Requests still authenticate with {name}. Unset it.")
