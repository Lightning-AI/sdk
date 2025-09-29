"""Studio SSH command."""

import subprocess
from typing import List, Optional

import click

from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.ssh_connection import download_ssh_keys
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.login import Auth


@click.command("ssh")
@click.option(
    "--name",
    help=(
        "The name of the studio to ssh into. "
        "If not provided, will try to infer from environment, "
        "use the default value from the config or prompt for interactive selection."
    ),
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
    return ssh_impl(name=name, teamspace=teamspace, option=option, vm=False)


def ssh_impl(name: Optional[str], teamspace: Optional[str], option: Optional[List[str]], vm: bool) -> None:
    auth = Auth()
    auth.authenticate()
    ssh_private_key_path = download_ssh_keys(auth.api_key, force_download=False)

    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    menu = StudiosMenu(resolved_teamspace, vm=vm)
    studio = menu(
        studio=name,
    )
    save_studio_to_config(studio)

    ssh_options = " -o " + " -o ".join(option) if option else ""
    ssh_command = f"ssh -i {ssh_private_key_path}{ssh_options} s_{studio._studio.id}@ssh.lightning.ai"

    try:
        subprocess.run(ssh_command.split())
    except Exception:
        # redownload the keys to be sure they are up to date
        download_ssh_keys(auth.api_key, force_download=True)
        try:
            subprocess.run(ssh_command.split())
        except Exception:
            # TODO: make this a generic CLI error
            raise RuntimeError("Failed to establish SSH connection") from None
