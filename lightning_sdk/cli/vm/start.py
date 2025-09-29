from typing import Optional

import click

from lightning_sdk.cli.studio.start import start_impl
from lightning_sdk.machine import CloudProvider, Machine


@click.command("start")
@click.option(
    "--name",
    help=(
        "The name of the VM to start. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option("--create", is_flag=True, help="Create the VM if it doesn't exist")
@click.option(
    "--machine",
    help="The machine type to start the VM on. Defaults to CPU-4",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli),
)
@click.option("--interruptible", is_flag=True, help="Start the VM on an interruptible instance.")
@click.option(
    "--cloud-provider",
    help=("The cloud provider to start the VM on. Defaults to teamspace default. Only used if --create is specified."),
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    help="The cloud account to start the VM on. Defaults to teamspace default. Only used if --create is specified.",
    type=click.STRING,
)
def start_vm(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    create: bool = False,
    machine: str = "CPU",
    interruptible: bool = False,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Start a VM.

    Example:
        lightning vm start --name my-vm

    """
    return start_impl(
        name=name,
        teamspace=teamspace,
        create=create,
        machine=machine,
        interruptible=interruptible,
        cloud_provider=cloud_provider,
        cloud_account=cloud_account,
        vm=True,
    )
