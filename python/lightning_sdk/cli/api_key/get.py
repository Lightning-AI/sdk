"""Get or create a model API key."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("get", cls=LightningCommand)
@click.option("--org", help=ORG_OPTION_HELP)
def get_api_key(org: Optional[str] = None) -> None:
    """Get a model API key for calling public inference endpoints.

    Mirrors the Model APIs page "Get API Key" button. Uses your current org
    automatically, returns an existing key when available, creates a default org
    key when needed, or falls back to your personal platform key.
    """
    api = ApiKeyApi()
    click.echo(api.get_or_create_default(org))
