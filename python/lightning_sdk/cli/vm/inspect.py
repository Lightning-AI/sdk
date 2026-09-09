"""VM inspect command."""

import json
from datetime import datetime
from typing import Any, Optional

import rich_click as click

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.vm.common import resolve_teamspace, resolve_vm


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


@click.command("inspect", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
def inspect_vm(name: str, teamspace: Optional[str] = None) -> None:
    """Inspect a virtual machine as JSON."""
    resolved_teamspace = resolve_teamspace(teamspace)
    vm = resolve_vm(VMApi(), resolved_teamspace, name)
    click.echo(json.dumps(_json_safe(vm.to_dict()), indent=2, sort_keys=True))
