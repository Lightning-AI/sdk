"""Studio connect command."""

import subprocess
import sys
from contextlib import suppress
from typing import Optional

import click

from lightning_sdk.cli.utils.get_base_studio import get_base_studio_id
from lightning_sdk.cli.utils.handle_machine_and_gpus_args import handle_machine_and_gpus_args
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config, save_teamspace_to_config
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.studio import Studio
from lightning_sdk.utils.names import random_unique_name


def _parse_args_or_get_from_current_studio(
    teamspace: Optional[str],
    cloud_account: Optional[str],
    studio_type: Optional[str],
    machine: Optional[str],
    gpus: Optional[str],
    cloud_provider: Optional[str],
    name: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    # Parse args provided by user
    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace)
    save_teamspace_to_config(resolved_teamspace, overwrite=False)

    template_id = get_base_studio_id(studio_type)

    if cloud_provider is not None:
        cloud_provider = CloudProvider(cloud_provider)

    name = name or random_unique_name()

    with suppress(ValueError):
        # Gets current studio context to use its parameters as defaults
        s = Studio()
        if not teamspace:
            resolved_teamspace = s.teamspace
            save_teamspace_to_config(resolved_teamspace, overwrite=False)
        if not cloud_account:
            cloud_account = s.cloud_account
        if not template_id:
            template_id = s._studio.environment_template_id
        if not machine and not gpus:
            machine = s.machine

    return resolved_teamspace, cloud_account, template_id, machine, cloud_provider, name


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
@click.option(
    "--machine",
    help="The machine type to start the studio on. Defaults to CPU-4",
    type=click.Choice(m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli),
)
@click.option(
    "--gpus",
    help="The number and type of GPUs to start the studio on (format: TYPE:COUNT, e.g. L4:4)",
    type=click.STRING,
)
@click.option(
    "--studio-type",
    help="The base studio template name to use for creating the studio. "
    "Must be lowercase and hyphenated (use '-' instead of spaces). "
    "Run 'lightning base-studio list' to see all available templates. "
    "Defaults to the first available template.",
    type=click.STRING,
)
@click.option("--interruptible", is_flag=True, help="Start the studio on an interruptible instance.")
def connect_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
    machine: Optional[str] = None,
    gpus: Optional[str] = None,
    studio_type: Optional[str] = None,
    interruptible: bool = False,
) -> None:
    """Connect to a Studio.

    Example:
        lightning studio connect
    """
    teamspace, cloud_account, template_id, machine, cloud_provider, name = _parse_args_or_get_from_current_studio(
        teamspace, cloud_account, studio_type, machine, gpus, cloud_provider, name
    )

    try:
        studio = Studio(
            name=name,
            teamspace=teamspace,
            create_ok=True,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
            studio_type=template_id,
        )
    except (RuntimeError, ValueError, ApiException):
        raise ValueError(f"Could not create Studio: '{name}'") from None

    click.echo(f"Connecting to Studio '{studio_name_link(studio)}' ...")

    Studio.show_progress = True

    machine = handle_machine_and_gpus_args(machine, gpus)

    save_studio_to_config(studio)
    studio.start(machine=machine, interruptible=interruptible)

    ssh_private_key_path = configure_ssh_internal()

    ssh_option = "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR"
    try:
        ssh_command = f"ssh -i {ssh_private_key_path} {ssh_option} s_{studio._studio.id}@ssh.lightning.ai"
        subprocess.run(ssh_command.split())
    except Exception as ex:
        print(f"Failed to establish SSH connection: {ex}")
        sys.exit(1)
