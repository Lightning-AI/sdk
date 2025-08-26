"""Studio SSH command."""

import os
import platform
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional

import click

from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.studio_selection import StudiosMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.utils.config import _DEFAULT_CONFIG_FILE_PATH


@click.command("ssh")
@click.option(
    "--name",
    help=(
        "The name of the studio to start. "
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
    auth = Auth()
    auth.authenticate()
    ssh_private_key_path = _download_ssh_keys(auth.api_key, force_download=False)

    menu = TeamspacesMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    menu = StudiosMenu(resolved_teamspace)
    studio = menu(studio=name)
    save_studio_to_config(studio)

    ssh_options = " -o " + " -o ".join(option) if option else ""
    ssh_command = f"ssh -i {ssh_private_key_path}{ssh_options} s_{studio._studio.id}@ssh.lightning.ai"

    try:
        subprocess.run(ssh_command.split())
    except Exception:
        # redownload the keys to be sure they are up to date
        _download_ssh_keys(auth.api_key, force_download=True)
        try:
            subprocess.run(ssh_command.split())
        except Exception:
            # TODO: make this a generic CLI error
            raise RuntimeError("Failed to establish SSH connection") from None


def _download_ssh_keys(
    api_key: str,
    force_download: bool = False,
    ssh_key_name: str = "lightning_rsa",
) -> None:
    """Download the SSH key for a User."""
    ssh_private_key_path = os.path.join(os.path.expanduser(os.path.dirname(_DEFAULT_CONFIG_FILE_PATH)), ssh_key_name)

    os.makedirs(os.path.dirname(ssh_private_key_path), exist_ok=True)

    if not os.path.isfile(ssh_private_key_path) or force_download:
        key_id = str(uuid.uuid4())
        _download_file(
            f"https://lightning.ai/setup/ssh-gen?t={api_key}&id={key_id}&machineName={platform.node()}",
            ssh_private_key_path,
            overwrite=True,
            chmod=0o600,
        )
        _download_file(
            f"https://lightning.ai/setup/ssh-public?t={api_key}&id={key_id}",
            ssh_private_key_path + ".pub",
            overwrite=True,
        )

    return ssh_private_key_path


def _download_file(url: str, local_path: Path, overwrite: bool = True, chmod: Optional[int] = None) -> None:
    """Download a file from a URL."""
    import requests

    if os.path.isfile(local_path) and not overwrite:
        raise FileExistsError(f"The file {local_path} already exists and overwrite is set to False.")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(local_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    if chmod is not None:
        os.chmod(local_path, 0o600)
