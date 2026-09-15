"""VM create command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.vm.common import MACHINE_VALUES, friendly_error, resolve_teamspace
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine
from lightning_sdk.vm import VM


@click.command("create", cls=LightningCommand)
@click.argument("name")
@click.option("--machine", required=True, type=click.Choice(MACHINE_VALUES, case_sensitive=False), help="Machine type.")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace).")
@click.option(
    "--cloud",
    "cloud_account",
    help=(
        "Cloud account (cluster id) to create the VM in. "
        "Defaults to the organization's machine cluster when there is exactly one."
    ),
)
@click.option("--volume-size", type=click.IntRange(400, 800), help="Root disk size in GB (400-800).")
@click.option("--spot", is_flag=True, default=False, help="Use an interruptible machine.")
@click.option("--wait", is_flag=True, default=False, help="Block until the VM is running, then print the SSH command.")
@click.option("--timeout", type=float, default=600.0, show_default=True, help="Seconds to wait with --wait.")
def create_vm(
    name: str,
    machine: str,
    teamspace: Optional[str] = None,
    cloud_account: Optional[str] = None,
    volume_size: Optional[int] = None,
    spot: bool = False,
    wait: bool = False,
    timeout: float = 600.0,
) -> None:
    """Create a virtual machine."""
    resolved_teamspace = resolve_teamspace(teamspace)
    try:
        vm = VM.create(
            name=name,
            machine=Machine.from_str(machine),
            teamspace=resolved_teamspace,
            cloud_account=cloud_account,
            volume_size=volume_size,
            spot=spot,
            wait=wait,
            timeout=timeout,
        )
    except ApiException as ex:
        raise friendly_error(ex) from ex
    except TimeoutError as ex:
        raise click.ClickException(
            f"{ex} The VM still exists; delete it with 'lightning vm delete <name>' if you no longer need it."
        ) from ex
    except (RuntimeError, ValueError) as ex:
        raise click.ClickException(str(ex)) from ex

    click.echo(f"Created VM {vm.name} ({vm.id}), status: {vm.status}")
    if vm.ssh_command:
        click.echo(f"Connect with: {vm.ssh_command}")
    elif not wait:
        click.echo(f"Run 'lightning vm ssh {vm.name}' once it is running.")
