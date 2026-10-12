"""lightning code setup: point a coding tool at code.lightning.ai."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.code import account
from lightning_sdk.cli.code import tool as tools
from lightning_sdk.cli.code.models import DEFAULT_MODEL, coding_models
from lightning_sdk.cli.code.registry import TOOL_NAMES, TOOLS
from lightning_sdk.cli.code.tool import KeyRecord, ToolConfigError
from lightning_sdk.cli.utils.logging import LightningCommand

# stands in for the key in a --dry-run, which doesn't create one
_DRY_RUN_KEY = "sk-lit-dry-run"


@click.command("setup", cls=LightningCommand)
@click.argument("tool", type=click.Choice(TOOL_NAMES, case_sensitive=False))
@click.option("--org", help="Organization that pays, by name. Asked for when you belong to several.")
@click.option(
    "--model",
    help=(
        f"Make this the default model, e.g. glm-5.3. Without it, {DEFAULT_MODEL} "
        "becomes the default only if you have none."
    ),
)
@click.option("--rotate-key", is_flag=True, default=False, help="Create a new API key and revoke the old one.")
@click.option("--dry-run", is_flag=True, default=False, help="Show the changes without writing or creating anything.")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Replace a Lightning setup that `lightning code` didn't make.",
)
def setup(tool: str, org: Optional[str], model: Optional[str], rotate_key: bool, dry_run: bool, force: bool) -> None:
    """Set up a coding tool to use code.lightning.ai.

    TOOL is one of opencode, pi, codex, dsh (DeepSeek Harness) or cursor. Lightning is
    added as a model provider without touching the rest of the tool's config, with an
    API key that bills the organization you choose. The organization needs a Pro, Teams
    or Enterprise plan. Cursor can't be configured from outside, so for it the key is
    printed with the steps to add it in Cursor Settings.

    Run it again to switch organizations or pick up new models.

    Examples:
        lightning code setup opencode --org my-org
        lightning code setup codex --org my-org --model glm-5.3
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

    previous = state.record
    chosen = account.choose_org(org, previous_org_id=previous.org_id if previous else None)
    account.require_coding_plan(chosen)

    # the key set up before, when the tool still has it, it bills the chosen org and it still exists
    reuse = (
        previous is not None
        and state.key is not None
        and not rotate_key
        and previous.org_id == chosen.id
        and account.key_exists(chosen.id, previous.key_id)
    )

    if dry_run:
        record = previous if reuse and previous else KeyRecord(chosen.id, chosen.name, "", "")
        plan = target.plan_setup(state, models=models, model=model, key=_DRY_RUN_KEY, record=record)
        click.echo(plan.describe() or f"No changes to {target.name}'s config.")
        if reuse and previous:
            click.echo(f"Would keep the API key '{previous.key_name}'.")
        else:
            click.echo(f"Would create an API key billed to {chosen.label}.")
            if previous is not None:
                click.echo(f"Would revoke the API key '{previous.key_name}' set up before.")
        return

    if reuse and previous and state.key:
        key, record = state.key, previous
    else:
        name = account.default_key_name(tool)
        created = account.create_key(
            chosen, name, f"For {target.name} on code.lightning.ai, created by `lightning code setup`"
        )
        key, record = created.raw_key, KeyRecord(chosen.id, chosen.name, created.id, name)

    plan = target.plan_setup(state, models=models, model=model, key=key, record=record)
    try:
        backups = tools.apply(plan)
    except Exception:
        if record is not previous:
            account.revoke_key(chosen.id, record.key_id)
        raise

    click.echo(f"{target.name} now uses code.lightning.ai, billed to {chosen.label}.")
    lines = [*target.summary(state, plan), ("API key", record.key_name)]
    if plan.set_model:
        lines.append(("Default", plan.set_model))
    lines += [("Backup", str(path)) for path in backups]
    width = max(len(label) for label, _ in lines) + 1
    for label, value in lines:
        click.echo(f"  {label + ':':<{width}} {value}")

    if previous is not None and record is not previous:
        if account.revoke_key(previous.org_id, previous.key_id):
            click.echo(f"Revoked the previous API key '{previous.key_name}'.")
        else:
            click.echo(
                f"Couldn't revoke the previous API key {previous.key_id}. "
                f"Delete it with: lightning api-key delete {previous.key_id} --org {previous.org_name}"
            )

    for note in target.warnings(state):
        click.echo(f"Note: {note}")
    instructions = target.instructions(key, models, plan)
    if instructions:
        click.echo(f"\n{instructions}")
    if not target.installed():
        click.echo(f"\n{target.name} isn't on your PATH. Install it with:\n  {target.install}")
    if target.start:
        click.echo(f"\n{target.start}")
