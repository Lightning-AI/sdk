"""lightning code status: which coding tools use code.lightning.ai."""

import rich_click as click

from lightning_sdk.cli.code import opencode
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.utils.jsonc import JSONCError


@click.command("status", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def status(as_json: bool = False) -> None:
    """Show which coding tools are set up for code.lightning.ai, and which org they bill."""
    try:
        state = opencode.read_state()
    except (JSONCError, ValueError) as exc:
        raise click.ClickException(f"Couldn't read OpenCode's config: {exc}") from None

    credential = state.credential
    metadata = credential.metadata if credential else {}
    info = {
        "tool": "opencode",
        "installed": opencode.installed(),
        "configured": state.provider is not None and credential is not None,
        "managed": state.managed,
        "config": str(state.config_path),
        "org": metadata.get("org_name"),
        "key_name": metadata.get("key_name"),
        "key_id": metadata.get("key_id"),
        "model": state.model,
    }
    if as_json:
        echo_json([info])
        return

    click.echo(opencode.NAME)
    if not info["configured"]:
        missing = "provider" if state.provider is None else "API key"
        if state.provider is None and credential is None:
            click.echo("  Not set up. Run: lightning code setup opencode")
        else:
            click.echo(f"  Incomplete, the {missing} is missing. Run: lightning code setup opencode")
        return
    if not state.managed:
        click.echo(f"  Set up by hand in {state.config_path}, not by `lightning code`.")
        return
    click.echo(f"  Org:     {info['org']}")
    click.echo(f"  API key: {info['key_name']} ({info['key_id']})")
    click.echo(f"  Config:  {info['config']}")
    click.echo(f"  Default: {info['model'] or 'none'}")
    if not info["installed"]:
        click.echo(f"  OpenCode isn't on your PATH. Install it with: {opencode.INSTALL_COMMAND}")
    for note in opencode.warnings(state):
        click.echo(f"  Note: {note}")
