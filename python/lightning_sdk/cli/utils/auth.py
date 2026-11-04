"""Authentication helpers shared by the CLI commands."""

from contextlib import contextmanager
from typing import Generator

import rich_click as click

from lightning_sdk.lightning_cloud.credentials import browser_login
from lightning_sdk.lightning_cloud.login import Auth


@contextmanager
def browser_authentication(allowed: bool) -> Generator[None, None, None]:
    """Temporarily control whether missing credentials may start browser authentication."""
    with browser_login(allowed):
        yield


def require_auth_header() -> str:
    """Return available credentials without falling back to browser authentication."""
    try:
        header = Auth().auth_header
    except (ValueError, ConnectionError) as err:
        raise click.UsageError(str(err)) from err
    if not header:
        raise click.UsageError("No Lightning credentials are available. Run `lightning login` first.")
    return header
