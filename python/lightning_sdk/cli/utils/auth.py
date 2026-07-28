"""Non-interactive authentication helpers for CLI commands."""

import rich_click as click

from lightning_sdk.lightning_cloud.login import Auth


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
