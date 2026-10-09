"""lightning code setup: point a coding tool at code.lightning.ai."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.code import account, opencode
from lightning_sdk.cli.code.models import MODEL_KEYS
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.utils.jsonc import JSONCError


@click.command("setup", cls=LightningCommand)
@click.argument("tool", type=click.Choice(["opencode"], case_sensitive=False))
@click.option("--org", help="Organization that pays, by name. Asked for when you belong to several.")
@click.option(
    "--model",
    type=click.Choice(MODEL_KEYS),
    help="Make this the default model. Without it, GLM-5.3 becomes the default only if you have none.",
)
@click.option("--rotate-key", is_flag=True, default=False, help="Create a new API key and revoke the old one.")
@click.option("--dry-run", is_flag=True, default=False, help="Show the changes without writing or creating anything.")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Replace a 'lightning' provider or key that `lightning code` didn't set up.",
)
def setup(tool: str, org: Optional[str], model: Optional[str], rotate_key: bool, dry_run: bool, yes: bool) -> None:
    """Set up a coding tool to use code.lightning.ai.

    Adds Lightning as a model provider without touching the rest of the tool's config,
    and creates an API key that bills the organization you choose. The organization
    needs a Pro, Teams or Enterprise plan. Run it again to switch organizations or
    pick up new models.

    Examples:
        lightning code setup opencode --org my-org
    """
    try:
        state = opencode.read_state()
    except (JSONCError, ValueError) as exc:
        raise click.ClickException(f"Couldn't read OpenCode's config: {exc}") from None

    if state.foreign and not yes:
        raise click.ClickException(
            f"OpenCode already has a '{opencode.PROVIDER_ID}' provider or key that `lightning code` didn't set up.\n"
            "Re-run with --yes to replace it. The config file is backed up first."
        )

    previous = state.credential if state.managed else None
    chosen = account.choose_org(org, previous_org_id=previous.org_id if previous else None)
    account.require_coding_plan(chosen)

    # the key set up before, when it bills the chosen org and still exists
    reuse = None
    if previous is not None and not rotate_key and previous.org_id == chosen.id and previous.key_id:
        reuse = previous if account.key_exists(chosen.id, previous.key_id) else None
    plan = opencode.plan_setup(state, model=model)

    if dry_run:
        diff = plan.config_diff()
        click.echo(diff if diff else f"No changes to {state.config_path}")
        if reuse:
            click.echo(f"Would keep the API key '{reuse.metadata.get('key_name', reuse.key_id)}'.")
        else:
            click.echo(f"Would create an API key billed to {chosen.label} and save it to {opencode.auth_path()}.")
            if previous is not None and previous.key_id:
                click.echo("Would revoke the API key set up before.")
        return

    if reuse:
        key, metadata = reuse.key, dict(reuse.metadata)
    else:
        name = account.default_key_name(tool)
        created = account.create_key(
            chosen, name, "For OpenCode on code.lightning.ai, created by `lightning code setup`"
        )
        key = created.raw_key
        metadata = {"org_id": chosen.id, "org_name": chosen.name, "key_id": created.id, "key_name": name}
    metadata.pop("managed_by", None)

    try:
        backup = opencode.apply_setup(plan, key=key, metadata=metadata)
    except Exception:
        if not reuse:
            account.revoke_key(chosen.id, metadata["key_id"])
        raise

    click.echo(f"OpenCode now uses code.lightning.ai, billed to {chosen.label}.")
    click.echo(f"  Provider: {opencode.PROVIDER_ID} in {state.config_path}")
    click.echo(f"  API key:  {metadata['key_name']} in {opencode.auth_path()}")
    if plan.set_model:
        click.echo(f"  Default:  {plan.set_model}")
    if backup:
        click.echo(f"  Backup:   {backup}")

    if previous is not None and not reuse and previous.key_id and previous.org_id:
        if account.revoke_key(previous.org_id, previous.key_id):
            click.echo(f"Revoked the previous API key '{previous.metadata.get('key_name', previous.key_id)}'.")
        else:
            click.echo(
                f"Couldn't revoke the previous API key {previous.key_id}. "
                f"Delete it with: lightning api-key delete {previous.key_id} --org {previous.metadata.get('org_name')}"
            )

    for note in opencode.warnings(state):
        click.echo(f"Note: {note}")
    if not opencode.installed():
        click.echo(f"\nOpenCode isn't on your PATH. Install it with:\n  {opencode.INSTALL_COMMAND}")
    click.echo("\nStart coding with `opencode`, and switch models with /models.")
