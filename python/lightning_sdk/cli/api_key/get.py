"""Get or create a model API key."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.api_key_api import ApiKeyApi
from lightning_sdk.cli.api_key.common import ORG_OPTION_HELP
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("get", cls=LightningCommand)
@click.option("--org", help=ORG_OPTION_HELP)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def get_api_key(org: Optional[str] = None, as_json: bool = False) -> None:
    """Get a model API key for calling public inference endpoints.

    Mirrors the Model APIs page "Get API Key" button. Uses your current org
    automatically, returns an existing key when available, creates a default org
    key when needed, or falls back to your personal platform key.
    """
    api = ApiKeyApi()
    key = api.get_or_create_default(org)
    if as_json:
        echo_json({"api_key": key})
        return
    click.echo(key)
