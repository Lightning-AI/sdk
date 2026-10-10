"""lightning code status: which coding tools use code.lightning.ai."""

from typing import Any

import rich_click as click

from lightning_sdk.cli.code.registry import TOOLS
from lightning_sdk.cli.code.tool import ToolConfigError
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("status", cls=LightningCommand)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def status(as_json: bool = False) -> None:
    """Show which coding tools are set up for code.lightning.ai, and which org they bill."""
    infos: list[dict[str, Any]] = []
    for tool in TOOLS.values():
        info: dict[str, Any] = {"tool": tool.id, "installed": tool.installed()}
        try:
            state = tool.read()
        except ToolConfigError as exc:
            infos.append({**info, "configured": False, "managed": False, "error": str(exc)})
            continue
        record = state.record
        infos.append(
            {
                **info,
                "configured": state.configured,
                "managed": record is not None,
                "config": state.location,
                "org": record.org_name if record else None,
                "key_name": record.key_name if record else None,
                "key_id": record.key_id if record else None,
                "model": state.default_model,
                "notes": tool.warnings(state) if state.configured else [],
            }
        )

    if as_json:
        echo_json(infos)
        return

    for info in infos:
        tool = TOOLS[info["tool"]]
        if "error" in info:
            click.echo(f"{tool.name}: couldn't read its config: {info['error']}")
        elif not info["configured"]:
            click.echo(f"{tool.name}: not set up")
            continue
        elif not info["managed"]:
            click.echo(f"{tool.name}: set up by hand in {info['config']}, not by `lightning code`")
            continue
        else:
            click.echo(f"{tool.name}: billed to {info['org']}")
            click.echo(f"  API key: {info['key_name']} ({info['key_id']})")
            click.echo(f"  Config:  {info['config']}")
            if info["model"]:
                click.echo(f"  Default: {info['model']}")
            if not info["installed"] and tool.install:
                click.echo(f"  Not on your PATH. Install it with: {tool.install}")
            for note in info["notes"]:
                click.echo(f"  Note: {note}")
