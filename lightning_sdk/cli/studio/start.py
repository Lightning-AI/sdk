"""Studio start command."""

from typing import Optional

import click

from lightning_sdk.machine import CloudProvider, Machine


@click.command("start")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option("--create", is_flag=True, help="Create the studio if it doesn't exist")
@click.option(
    "--machine",
    help="The machine type to start the studio on.",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine)),
)
@click.option("--interruptible", is_flag=True, help="Start the studio on an interruptible instance.")
@click.option(
    "--cloud-provider",
    help="The cloud provider to start the studio on.",
    type=click.Choice(m.name for m in list(CloudProvider)),
)
def start_studio(
    studio_name: Optional[str] = None,
    teamspace: Optional[str] = None,
    create: bool = False,
    machine: Optional[str] = None,
    interruptible: bool = False,
    cloud_provider: Optional[str] = None,
) -> None:
    """Start a Studio."""
    raise NotImplementedError("Not implemented")
