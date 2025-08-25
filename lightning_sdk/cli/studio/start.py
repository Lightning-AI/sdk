"""Studio start command."""

from typing import Optional

import click

from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.studio import Studio


@click.command("start")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option("--create", is_flag=True, help="Create the studio if it doesn't exist")
@click.option(
    "--machine",
    help="The machine type to start the studio on. Defaults to CPU-4",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli),
)
@click.option("--interruptible", is_flag=True, help="Start the studio on an interruptible instance.")
@click.option(
    "--cloud-provider",
    help=(
        "The cloud provider to start the studio on. Defaults to teamspace default. "
        "Only used if --create is specified."
    ),
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    help="The cloud account to start the studio on. Defaults to teamspace default. Only used if --create is specified.",
    type=click.STRING,
)
def start_studio(
    studio_name: Optional[str] = None,
    teamspace: Optional[str] = None,
    create: bool = False,
    machine: Optional[str] = None,
    interruptible: bool = False,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
) -> None:
    """Start a Studio.

    Example:
        lightning studio start [STUDIO_NAME]

    STUDIO_NAME: the name of the studio to start.

    If STUDIO_NAME is not provided, will try to infer from environment or use the default value from the config.
    """
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)

    try:
        studio = Studio(
            studio_name,
            teamspace=resolved_teamspace,
            create_ok=create,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
        )
    except (RuntimeError, ValueError, ApiException):
        if studio_name:
            raise ValueError(f"Could not start Studio: '{studio_name}'. Does the Studio exist?") from None
        raise ValueError(f"Could not start Studio: '{studio_name}'. Please provide a Studio name") from None

    Studio.show_progress = True
    studio.start(machine, interruptible=interruptible)
    click.echo(f"Studio '{studio.name}' started successfully")
