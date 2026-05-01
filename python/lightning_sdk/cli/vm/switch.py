from typing import Optional

import click

from lightning_sdk.cli.studio.switch import switch_impl
from lightning_sdk.machine import Machine


@click.command("switch")
@click.option(
    "--name",
    help=(
        "The name of the VM to switch to a different machine. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--machine",
    help="The machine type to switch the studio to.",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine)),
)
@click.option("--interruptible", is_flag=True, help="Switch the studio to an interruptible instance.")
def switch_vm(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    machine: Optional[str] = None,
    interruptible: bool = False,
) -> None:
    """Switch a VM to a different machine type."""
    return switch_impl(
        name=name,
        teamspace=teamspace,
        machine=machine,
        interruptible=interruptible,
        vm=True,
    )
