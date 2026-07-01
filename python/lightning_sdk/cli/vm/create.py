from typing import Optional

import rich_click as click

from lightning_sdk.cli.studio.create import create_impl
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("create", cls=LightningCommand)
@click.option("--name", help="The name of the VM to create. If not provided, a random name will be generated.")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option("--cloud", help="Cloud provider or cloud account to create the VM on. Defaults to teamspace default.")
def create_vm(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud: Optional[str] = None,
) -> None:
    """Create a new VM.

    Example:
        lightning vm create
    """
    create_impl(name=name, teamspace=teamspace, cloud=cloud, vm=True)
