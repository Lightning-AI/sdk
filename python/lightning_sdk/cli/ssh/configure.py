"""SSH configure command."""

from pathlib import Path
from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.legacy.studios_menu import _StudiosMenu
from lightning_sdk.cli.ssh.common import generate_ssh_config
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.ssh_connection import download_file
from lightning_sdk.lightning_cloud.login import Auth


@click.command("configure", cls=LightningCommand)
@click.option(
    "--name",
    default=None,
    help=(
        "The name of the studio to obtain SSH config. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "The teamspace the studio is part of. "
        "Should be of format <OWNER>/<TEAMSPACE_NAME>. "
        "If not specified, tries to infer from the environment (e.g. when run from within a Studio.)"
    ),
)
@click.option(
    "--overwrite",
    is_flag=True,
    flag_value=True,
    default=False,
    help="Whether to overwrite the SSH key and config if they already exist.",
)
def configure_ssh(name: Optional[str] = None, teamspace: Optional[str] = None, overwrite: bool = False) -> None:
    """Get SSH config entry for a studio."""
    import platform
    import uuid

    auth = Auth()
    auth.authenticate()
    console = Console()
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    key_path = ssh_dir / "lightning_rsa"
    config_path = ssh_dir / "config"

    if not key_path.exists() or not (key_path.with_suffix(".pub")).exists() or overwrite:
        key_id = str(uuid.uuid4())
        download_file(
            f"https://lightning.ai/setup/ssh-gen?t={auth.api_key}&id={key_id}&machineName={platform.node()}",
            key_path,
            overwrite=overwrite,
            chmod=0o600,
        )
        download_file(
            f"https://lightning.ai/setup/ssh-public?t={auth.api_key}&id={key_id}",
            key_path.with_suffix(".pub"),
            overwrite=overwrite,
        )
        console.print(f"SSH key generated and saved to {key_path}")
    else:
        console.print(f"SSH key already exists at {key_path}")

    menu = _StudiosMenu()
    studio = menu._get_studio(name=name, teamspace=teamspace)
    config_content = generate_ssh_config(key_path=str(key_path), user=f"s_{studio._studio.id}", host=studio.name)
    if config_path.exists() and f"Host {studio.name}" in config_path.read_text():
        console.print("SSH config already contains the required configuration.")
        return

    with config_path.open("a") as config_file:
        config_file.write("\n")
        config_file.write(config_content)
        config_file.write("\n")
    console.print(f"SSH config updated at {config_path}")
