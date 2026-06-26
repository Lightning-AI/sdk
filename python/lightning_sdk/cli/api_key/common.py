"""Shared helpers for API key CLI commands."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.organization import Organization

ORG_OPTION_HELP = (
    "Optional organization override. For multiple orgs, set LIGHTNING_ORG or "
    "`lightning config set organization.name` to match the org selected in the web UI "
    "(the UI uses browser session storage, not the CLI config)."
)


def resolve_org(org_name: Optional[str] = None) -> Organization:
    """Resolve the organization to use for API key commands."""
    try:
        org = ApiKeyApi().resolve_org_context(org_name)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    if org is None:
        raise click.UsageError(
            "Could not determine an organization for this account. Pass --org <name> to choose one explicitly."
        )
    return org
