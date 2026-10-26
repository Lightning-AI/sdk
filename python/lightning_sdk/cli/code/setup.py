"""lightning code setup: point a coding tool at code.lightning.ai."""

import os
from typing import Optional

import rich_click as click

from lightning_sdk.cli.code import tool as tools
from lightning_sdk.cli.code.models import DEFAULT_MODEL, coding_models
from lightning_sdk.cli.code.registry import TOOL_NAMES, TOOLS
from lightning_sdk.cli.code.tool import ToolConfigError
from lightning_sdk.cli.utils.logging import LightningCommand

# the variable the key is read from, which the tool's config then holds
KEY_ENV = "LIGHTNING_API_KEY"
# stands in for the key in a --dry-run, which doesn't need one
_DRY_RUN_KEY = "lit_sa_dry-run"


@click.command("setup", cls=LightningCommand)
@click.argument("tool", type=click.Choice(TOOL_NAMES, case_sensitive=False))
@click.option(
    "--model",
    help=(
        f"Make this the default model, e.g. glm-5.3. Without it, {DEFAULT_MODEL} "
        "becomes the default only if you have none."
    ),
)
@click.option("--dry-run", is_flag=True, default=False, help="Show the changes without writing anything.")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Replace a Lightning setup that `lightning code` didn't make.",
)
def setup(tool: str, model: Optional[str], dry_run: bool, force: bool) -> None:
    """Set up a coding tool to use code.lightning.ai.

    TOOL is one of opencode, pi, codex, dsh (DeepSeek Harness) or cursor. Lightning is
    added as a model provider without touching the rest of the tool's config. The API
    key is read from LIGHTNING_API_KEY and saved in the tool's config; no key is created.
    Cursor can't be configured from outside, so for it the key is printed with the steps
    to add it in Cursor Settings.

    Run it again to pick up new models.

    Examples:
        LIGHTNING_API_KEY=lit_sa_... lightning code setup opencode
        LIGHTNING_API_KEY=lit_sa_... lightning code setup codex --model glm-5.3
    """
    target = TOOLS[tool.lower()]
    try:
        state = target.read()
    except ToolConfigError as exc:
        raise click.ClickException(f"Couldn't read {target.name}'s config: {exc}") from None

    if state.foreign and not force:
        raise click.ClickException(
            f"{target.name} already has a Lightning setup that `lightning code` didn't make ({state.location}).\n"
            "Re-run with --force to replace it. Files you had are backed up first."
        )

    models, fetch_error = coding_models()
    if fetch_error:
        click.echo(f"Couldn't get the model list from code.lightning.ai ({fetch_error}); using the built-in one.")
    keys = [m.key for m in models]
    if model is not None and model not in keys:
        raise click.UsageError(f"Unknown model '{model}'. Choose one of: {', '.join(keys)}")

    if dry_run:
        plan = target.plan_setup(state, models=models, model=model, key=_DRY_RUN_KEY)
        click.echo(plan.describe() or f"No changes to {target.name}'s config.")
        return

    key = os.environ.get(KEY_ENV)
    if not key:
        raise click.ClickException(f"Set {KEY_ENV} to the API key {target.name} should use, then run setup again.")

    plan = target.plan_setup(state, models=models, model=model, key=key)
    backups = tools.apply(plan)

    click.echo(f"{target.name} now uses code.lightning.ai.")
    lines = [*target.summary(state, plan)]
    if plan.set_model:
        lines.append(("Default", plan.set_model))
    lines += [("Backup", str(path)) for path in backups]
    width = max((len(label) for label, _ in lines), default=0) + 1
    for label, value in lines:
        click.echo(f"  {label + ':':<{width}} {value}")

    for note in target.warnings(state):
        click.echo(f"Note: {note}")
    instructions = target.instructions(key, models, plan)
    if instructions:
        click.echo(f"\n{instructions}")
    if not target.installed():
        click.echo(f"\n{target.name} isn't on your PATH. Install it with:\n  {target.install}")
    if target.start:
        click.echo(f"\n{target.start}")
