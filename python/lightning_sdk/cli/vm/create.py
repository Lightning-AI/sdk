from typing import Optional

import click

from lightning_sdk.cli.studio.create import create_impl
from lightning_sdk.machine import CloudProvider


@click.command("create")
@click.option("--name", help="The name of the VM to create. If not provided, a random name will be generated.")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--cloud-provider",
    help="The cloud provider to start the VM on. Defaults to teamspace default.",
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    help="The cloud account to create the VM on. Defaults to teamspace default.",
    type=click.STRING,
)
def create_vm(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Create a new VM.

    Example:
        lightning vm create
    """
    create_impl(name=name, teamspace=teamspace, cloud_provider=cloud_provider, cloud_account=cloud_account, vm=True)
