"""VM list command."""

from typing import Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.cli.vm.common import iter_teamspaces, org_id_for


@click.command("list", cls=LightningCommand)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option(
    "--all",
    "all_teamspaces",
    is_flag=True,
    flag_value=True,
    default=False,
    help="List VMs in all teamspaces visible to the selected owner.",
)
def list_vms(teamspace: Optional[str] = None, all_teamspaces: bool = False) -> None:
    """List virtual machines in a teamspace."""
    api = VMApi()
    rows = []
    for resolved_teamspace in iter_teamspaces(teamspace, all_teamspaces):
        org_id_for(resolved_teamspace)
        for vm in api.list_vms(resolved_teamspace.id):
            rows.append((resolved_teamspace, vm))

    table = Table(pad_edge=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Teamspace", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Machine", no_wrap=True)
    table.add_column("Created", no_wrap=True)
    table.add_column("SSH host", no_wrap=True)

    for resolved_teamspace, vm in sorted(rows, key=lambda row: row[1].name or ""):
        created = vm.created_at.strftime("%Y-%m-%d %H:%M") if vm.created_at else ""
        table.add_row(
            vm.name or "",
            f"{resolved_teamspace.owner.name}/{resolved_teamspace.name}",
            vm.status or "",
            vm.instance_type or "",
            created,
            vm.ssh_host or "",
        )

    click.echo(rich_to_str(table), color=True)
