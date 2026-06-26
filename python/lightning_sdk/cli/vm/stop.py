from typing import Optional

import rich_click as click

from lightning_sdk.cli.studio.stop import stop_impl
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("stop", cls=LightningCommand)
@click.option(
    "--name",
    help=(
        "The name of the VM to stop. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def stop_vm(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a VM.

    Example:
        lightning vm stop --name my-vm

    """
    return stop_impl(name=name, teamspace=teamspace, vm=True)
