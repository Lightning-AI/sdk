"""VM ssh command."""

import os
import shlex
from typing import Optional, Sequence

import rich_click as click

from lightning_sdk.api.vm_api import VMApi
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.vm.common import org_id_for, resolve_teamspace, resolve_vm


@click.command("ssh", cls=LightningCommand, context_settings={"ignore_unknown_options": True})
@click.argument("name")
@click.argument("ssh_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option(
    "--timeout", type=float, default=600.0, show_default=True, help="Seconds to wait for the VM to be running."
)
def ssh_vm(name: str, ssh_args: Sequence[str] = (), teamspace: Optional[str] = None, timeout: float = 600.0) -> None:
    """SSH into a virtual machine. Arguments after -- are passed to ssh."""
    resolved_teamspace = resolve_teamspace(teamspace)
    api = VMApi()
    vm = resolve_vm(api, resolved_teamspace, name)

    if vm.status != "running":
        click.echo(f"VM {vm.name} is {vm.status}; waiting for it to be running...", err=True)
        try:
            vm = api.wait_for_status(vm.id, org_id_for(resolved_teamspace), timeout=timeout)
        except (RuntimeError, TimeoutError) as ex:
            raise click.ClickException(str(ex)) from ex

    if not vm.ssh_command:
        raise click.ClickException(f"VM {vm.name} has no SSH command yet; try again in a moment.")

    argv = shlex.split(vm.ssh_command) + list(ssh_args)
    os.execvp(argv[0], argv)
