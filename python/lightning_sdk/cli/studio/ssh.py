"""Studio SSH command."""

import subprocess
from typing import List, Optional

import rich_click as click

from lightning_sdk.cli.resource_completion import complete_studio
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.ssh_connection import configure_ssh_internal


@click.command("ssh", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
    shell_complete=complete_studio,
)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)", type=click.STRING)
@click.option(
    "--option",
    "-o",
    help="Additional options to pass to the SSH command. Can be specified multiple times.",
    multiple=True,
    type=click.STRING,
)
def ssh_studio(name: Optional[str] = None, teamspace: Optional[str] = None, option: Optional[List[str]] = None) -> None:
    """SSH into a Studio.

    Example:
        lightning studio ssh --name my-studio
    """
    return ssh_impl(name=name, teamspace=teamspace, option=option)


def ssh_impl(name: Optional[str], teamspace: Optional[str], option: Optional[List[str]]) -> None:
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)
    save_studio_to_config(studio)

    ssh_private_key_path = configure_ssh_internal()

    ssh_options = " -o " + " -o ".join(option) if option else ""
    ssh_command = f"ssh -i {ssh_private_key_path}{ssh_options} s_{studio._studio.id}@ssh.lightning.ai"

    try:
        subprocess.run(ssh_command.split())
    except Exception:
        # redownload the keys to be sure they are up to date
        ssh_private_key_path = configure_ssh_internal(force_download=True)
        try:
            subprocess.run(ssh_command.split())
        except Exception:
            # TODO: make this a generic CLI error
            raise RuntimeError("Failed to establish SSH connection") from None
