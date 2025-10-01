"""Studio connect command."""

import subprocess
import sys
from typing import Dict, Optional, Set

import click

from lightning_sdk.base_studio import BaseStudio
from lightning_sdk.cli.utils.richt_print import studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config, save_teamspace_to_config
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import CloudProvider, Machine
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
@click.option(
    "--gpus",
    help="The number and type of GPUs to start the studio on (format: TYPE:COUNT, e.g. L4:4)",
    type=click.STRING,
)
@click.option(
    "--studio-type",
    help="The base studio template to use for creating the studio. Defaults to the first available template.",
    type=click.STRING,
)
def connect_studio(
    name: Optional[str] = None,
    teamspace: Optional[str] = None,
    cloud_provider: Optional[str] = None,
    cloud_account: Optional[str] = None,
    gpus: Optional[str] = None,
    studio_type: Optional[str] = None,
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

    # check for available base studios
    base_studios = BaseStudio()
    base_studios = base_studios.list()
    template_id = None
    if base_studios and len(base_studios):
        # if not specified by user, use the first existing template studio
        template_id = base_studios[0].id
        if studio_type:
            template_id = studio_type

    try:
        studio = Studio(
            name=name,
            teamspace=resolved_teamspace,
            create_ok=True,
            cloud_provider=cloud_provider,
            cloud_account=cloud_account,
            studio_type=template_id,
        )
    except (RuntimeError, ValueError, ApiException):
        raise ValueError(f"Could not create Studio: '{name}'") from None

    click.echo(f"Connecting to Studio '{studio_name_link(studio)}' ...")

    machine = "CPU"
    Studio.show_progress = True

    if gpus:
        gpus = gpus.strip()
        machine_name = gpus
        machine_num = 1

        machine_options = {
            m.name.lower(): m.name for m in Machine.__dict__.values() if isinstance(m, Machine) and m._include_in_cli
        }
        if ":" in gpus:
            machine_name, machine_val = gpus.split(":", 1)
            machine_name = machine_name.strip()
            machine_val = machine_val.strip()

            if not machine_val.isdigit() or int(machine_val) <= 0:
                raise ValueError(f"Invalid GPU count '{machine_val}'. Must be a positive integer.")
            machine_num = int(machine_val)

        if machine_num == 1:
            # e.g. gpus=L4 or gpus=L4:1
            gpu_key = machine_name.lower()
            if gpu_key not in machine_options:
                raise ValueError(
                    f"Invalid GPU type '{machine_name}'. "
                    f"Available options: {', '.join(_construct_available_gpus(machine_options))}"
                )
            machine = machine_options[gpu_key]
        else:
            # e.g. gpus=L4:4
            gpu_key = f"{machine_name.lower()}_x_{machine_num}"
            if gpu_key not in machine_options:
                raise ValueError(
                    f"Invalid GPU configuration '{gpus}'. "
                    f"Available options: {', '.join(_construct_available_gpus(machine_options))}"
                )
            machine = machine_options[gpu_key]

    save_studio_to_config(studio)
    # by default, interruptible is False
    studio.start(machine=machine, interruptible=False)

    ssh_private_key_path = configure_ssh_internal()

    ssh_option = "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR"
    try:
        ssh_command = f"ssh -i {ssh_private_key_path} {ssh_option} s_{studio._studio.id}@ssh.lightning.ai"
        subprocess.run(ssh_command.split())
    except Exception as ex:
        print(f"Failed to establish SSH connection: {ex}")
        sys.exit(1)


def _construct_available_gpus(machine_options: Dict[str, str]) -> Set[str]:
    # returns available gpus:count
    available_gpus = set()
    for v in machine_options.values():
        if "_X_" in v:
            gpu_type_num = v.replace("_X_", ":")
            available_gpus.add(gpu_type_num)
        else:
            available_gpus.add(v)
    return available_gpus
