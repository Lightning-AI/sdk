"""Studio connect command."""

import subprocess
import sys
from typing import Optional

import click

from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config, save_teamspace_to_config
from lightning_sdk.cli.utils.ssh_connection import download_ssh_keys
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider
from lightning_sdk.studio import Studio
from lightning_sdk.utils.names import random_unique_name


@click.command("connect")
@click.argument("name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--cloud-provider",
    help="The cloud provider to start the studio on. Defaults to teamspace default.",
    type=click.Choice(m.name for m in list(CloudProvider)),
)
@click.option(
    "--cloud-account",
    help="The cloud account to create the studio on. Defaults to teamspace default.",
    type=click.STRING,
)
@click.option("--gpus", help="The number of GPUs to start the studio on. ", type=click.INT)
def connect_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
    gpus: Optional[int] = None,
) -> None:
    """Connect to a Studio.

    Example:
        lightning studio connect
    """
    menu = TeamspacesMenu()

    resolved_teamspace = menu(teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)

    name = name or random_unique_name()

    try:
        studio = Studio(
            name=name,
            teamspace=resolved_teamspace,
            create_ok=True,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
        )
    except (RuntimeError, ValueError, ApiException):
        raise ValueError(f"Could not create Studio: '{name}'") from None

    click.echo(f"Connecting to Studio '{studio_name_link(studio)}' ...")

    machine = "CPU"
    Studio.show_progress = True
    if gpus:
        # TODO: handle something like gpus=4:L4
        pass

    save_studio_to_config(studio)
    studio.start(machine, interruptible=True)

    ssh_private_key_path = _configure_ssh_internal()

    try:
        ssh_command = (
            f"ssh -i {ssh_private_key_path} -o UserKnownHostsFile=/dev/null s_{studio._studio.id}@ssh.lightning.ai"
        )
        subprocess.run(ssh_command.split())
    except Exception as ex:
        print(f"Failed to establish SSH connection: {ex}")
        sys.exit(1)


def _configure_ssh_internal() -> str:
    """Internal function to configure SSH without Click decorators."""
    auth = Auth()
    auth.authenticate()
    return download_ssh_keys(auth.api_key, force_download=False)
