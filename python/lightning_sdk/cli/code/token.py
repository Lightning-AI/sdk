"""lightning code token: create an API key for any coding tool."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.code import account
from lightning_sdk.cli.code.models import CODE_BASE_URL
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("token", cls=LightningCommand)
@click.option("--org", help="Organization that pays, by name. Asked for when you belong to several.")
@click.option("--name", help='Name for the key. Defaults to "code.lightning.ai on <host> <date>".')
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Output the key, its org and the base URL as JSON."
)
def token(org: Optional[str], name: Optional[str], as_json: bool = False) -> None:
    """Create an API key for code.lightning.ai and print it.

    For tools `lightning code setup` doesn't configure: Claude Code, Cursor, Cline,
    or your own scripts. The key bills the organization you choose, which needs a
    Pro, Teams or Enterprise plan. It's shown only once.

    Examples:
        export OPENAI_API_KEY=$(lightning code token --org my-org)
        export OPENAI_BASE_URL=https://code.lightning.ai/v1
    """
    chosen = account.choose_org(org)
    account.require_coding_plan(chosen)
    key_name = name or account.default_key_name("code.lightning.ai")
    created = account.create_key(chosen, key_name, "For code.lightning.ai, created by `lightning code token`")

    if as_json:
        echo_json(
            {
                "api_key": created.raw_key,
                "base_url": CODE_BASE_URL,
                "key_id": created.id,
                "key_name": key_name,
                "org": chosen.name,
                "org_id": chosen.id,
            }
        )
        return
    click.echo(created.raw_key)
