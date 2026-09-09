"""VM delete command."""

from typing import Optional

import rich_click as click

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.vm.common import friendly_error, org_id_for, resolve_teamspace, resolve_vm
from lightning_sdk.lightning_cloud.openapi.rest import ApiException


@click.command("delete", cls=LightningCommand)
@click.argument("name")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option("--yes", "-y", is_flag=True, default=False, help="Do not prompt for confirmation.")
def delete_vm(name: str, teamspace: Optional[str] = None, yes: bool = False) -> None:
    """Delete a virtual machine. This discards its disk."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = VMApi()
    vm = resolve_vm(api, resolved_teamspace, name)

    if not yes:
        click.confirm(f"Delete VM {vm.name}? Its disk will be discarded.", abort=True)

    try:
        api.delete_vm(vm.id, org_id_for(resolved_teamspace))
    except ApiException as ex:
        raise friendly_error(ex) from ex
    click.echo(f"Deleted VM {vm.name}.")
