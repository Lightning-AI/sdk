"""lightning code remove: undo `lightning code setup`."""

import rich_click as click

from lightning_sdk.cli.code import account
from lightning_sdk.cli.code import tool as tools
from lightning_sdk.cli.code.registry import TOOL_NAMES, TOOLS
from lightning_sdk.cli.code.tool import ToolConfigError
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("remove", cls=LightningCommand)
@click.argument("tool", type=click.Choice(TOOL_NAMES, case_sensitive=False))
@click.option("--keep-key", is_flag=True, default=False, help="Leave the API key active instead of revoking it.")
def remove(tool: str, keep_key: bool) -> None:
    """Stop a coding tool from using code.lightning.ai.

    Removes the Lightning provider, the default model if it's a Lightning one, and the
    API key, which is also revoked. The rest of the tool's config is left alone.

    Examples:
        lightning code remove opencode
    """
    target = TOOLS[tool.lower()]
    try:
        state = target.read()
    except ToolConfigError as exc:
        raise click.ClickException(f"Couldn't read {target.name}'s config: {exc}") from None

    record = state.record
    plan = target.plan_remove(state)
    if not plan.removed and record is None:
        click.echo(f"{target.name} isn't set up for code.lightning.ai.")
        return
    tools.apply(plan)
    for item in plan.removed:
        click.echo(f"Removed {item}")
    if target.removal_instructions():
        click.echo(target.removal_instructions())

    if record is None:
        return
    if keep_key:
        click.echo(f"The API key '{record.key_name}' is still active.")
    elif account.revoke_key(record.org_id, record.key_id):
        click.echo(f"Revoked the API key '{record.key_name}'.")
    else:
        click.echo(
            f"Couldn't revoke the API key {record.key_id}. Delete it with: "
            f"lightning api-key delete {record.key_id} --org {record.org_name}"
        )
