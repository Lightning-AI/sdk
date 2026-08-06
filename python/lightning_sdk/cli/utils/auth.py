"""Non-interactive authentication helpers for CLI commands."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional

import rich_click as click

from lightning_sdk.lightning_cloud.login import Auth

_BROWSER_AUTH_ALLOWED = ContextVar("lightning_browser_auth_allowed", default=True)


@contextmanager
def browser_authentication(allowed: bool) -> Generator[None, None, None]:
    """Temporarily control whether missing credentials may start browser authentication."""
    token = _BROWSER_AUTH_ALLOWED.set(allowed)
    authenticate = Auth.authenticate

    def guarded_authenticate(auth: Auth) -> Optional[str]:
        if _BROWSER_AUTH_ALLOWED.get():
            return authenticate(auth)

        has_own_run_server = "_run_server" in auth.__dict__
        run_server = auth.__dict__.get("_run_server")

        def blocked_run_server() -> None:
            raise ValueError("No Lightning credentials are available. Run `lightning login` first.")

        auth.__dict__["_run_server"] = blocked_run_server
        try:
            return authenticate(auth)
        finally:
            if has_own_run_server:
                auth.__dict__["_run_server"] = run_server
            else:
                auth.__dict__.pop("_run_server", None)

    Auth.authenticate = guarded_authenticate
    try:
        yield
    finally:
        Auth.authenticate = authenticate
        _BROWSER_AUTH_ALLOWED.reset(token)


def require_auth_header() -> str:
    """Return available credentials without falling back to browser authentication."""
    auth = Auth()
    try:
        header = auth.auth_header
    except ValueError:
        header = None

    if header:
        return header

    if auth.load():
        try:
            header = auth.auth_header
        except ValueError:
            header = None
        if header:
            return header

    raise click.UsageError("No Lightning credentials are available. Run `lightning login` first.")
