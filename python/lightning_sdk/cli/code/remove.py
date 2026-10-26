"""lightning code remove: undo `lightning code setup`."""

import rich_click as click

from lightning_sdk.cli.code import tool as tools
from lightning_sdk.cli.code.registry import TOOL_NAMES, TOOLS
from lightning_sdk.cli.code.tool import ToolConfigError
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("remove", cls=LightningCommand)
@click.argument("tool", type=click.Choice(TOOL_NAMES, case_sensitive=False))
def remove(tool: str) -> None:
    """Stop a coding tool from using code.lightning.ai.

    Removes the Lightning provider, the default model if it's a Lightning one, and the
    API key saved in the tool's config. The rest of the tool's config is left alone.

    Examples:
        lightning code remove opencode
    """
    target = TOOLS[tool.lower()]
    try:
        state = target.read()
    except ToolConfigError as exc:
        raise click.ClickException(f"Couldn't read {target.name}'s config: {exc}") from None

    plan = target.plan_remove(state)
    if not plan.removed and not state.managed:
        click.echo(f"{target.name} isn't set up for code.lightning.ai.")
        return
    tools.apply(plan)
    for item in plan.removed:
        click.echo(f"Removed {item}")
    if target.removal_instructions():
        click.echo(target.removal_instructions())
