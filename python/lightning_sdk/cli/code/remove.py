"""lightning code remove: undo `lightning code setup`."""

import rich_click as click

from lightning_sdk.cli.code import account, opencode
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.utils.jsonc import JSONCError


@click.command("remove", cls=LightningCommand)
@click.argument("tool", type=click.Choice(["opencode"], case_sensitive=False))
@click.option("--keep-key", is_flag=True, default=False, help="Leave the API key active instead of revoking it.")
def remove(tool: str, keep_key: bool) -> None:
    """Stop a coding tool from using code.lightning.ai.

    Removes the Lightning provider, the default model if it's a Lightning one, and the
    API key, which is also revoked. The rest of the tool's config is left alone.

    Examples:
        lightning code remove opencode
    """
    try:
        state = opencode.read_state()
    except (JSONCError, ValueError) as exc:
        raise click.ClickException(f"Couldn't read OpenCode's config: {exc}") from None

    credential = state.credential if state.managed else None
    removed = opencode.remove(state)
    if not removed:
        click.echo("OpenCode isn't set up for code.lightning.ai.")
        return
    for item in removed:
        click.echo(f"Removed {item}")

    if credential is None or not credential.key_id or not credential.org_id:
        return
    name = credential.metadata.get("key_name", credential.key_id)
    if keep_key:
        click.echo(f"The API key '{name}' is still active.")
    elif account.revoke_key(credential.org_id, credential.key_id):
        click.echo(f"Revoked the API key '{name}'.")
    else:
        click.echo(
            f"Couldn't revoke the API key {credential.key_id}. Delete it with: "
            f"lightning api-key delete {credential.key_id} --org {credential.metadata.get('org_name')}"
        )
