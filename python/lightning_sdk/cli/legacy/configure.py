import os
import platform
import uuid
from pathlib import Path
from typing import Optional, Union

import click
from rich.console import Console

from lightning_sdk.cli.legacy.generate import _generate_ssh_config
from lightning_sdk.cli.legacy.studios_menu import _StudiosMenu
from lightning_sdk.lightning_cloud.login import Auth


@click.group(name="configure")
def configure() -> None:
    """Configure access to resources on the Lightning AI platform."""


def _configure_ssh_internal(
    name: Optional[str] = None, teamspace: Optional[str] = None, overwrite: bool = False
) -> None:
    """Internal function to configure SSH without Click decorators."""
    auth = Auth()
    auth.authenticate()
    console = Console()
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    key_path = ssh_dir / "lightning_rsa"
    config_path = ssh_dir / "config"

    # Check if the SSH key already exists
    if key_path.exists() and (key_path.with_suffix(".pub")).exists() and not overwrite:
        console.print(f"SSH key already exists at {key_path}")
    else:
        _download_ssh_keys(auth.api_key, ssh_home=ssh_dir, ssh_key_name="lightning_rsa", overwrite=overwrite)
        console.print(f"SSH key generated and saved to {key_path}")

    # Check if the SSH config already contains the required configuration
    menu = _StudiosMenu()
    studio = menu._get_studio(name=name, teamspace=teamspace)
    config_content = _generate_ssh_config(key_path=str(key_path), user=f"s_{studio._studio.id}", host=studio.name)
    if config_path.exists():
        with config_path.open("r") as config_file:
            # check if the host already exists in the config
            if f"Host {studio.name}" in config_file.read():
                console.print("SSH config already contains the required configuration.")
                return

    with config_path.open("a") as config_file:
        config_file.write(os.linesep)
        config_file.write(config_content)
        config_file.write(os.linesep)
        console.print(f"SSH config updated at {config_path}")


@configure.command(name="ssh")
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
def ssh(name: Optional[str] = None, teamspace: Optional[str] = None, overwrite: bool = False) -> None:
    """Get SSH config entry for a studio."""
    _configure_ssh_internal(name=name, teamspace=teamspace, overwrite=overwrite)


def _download_file(url: str, local_path: Path, overwrite: bool = True, chmod: Optional[int] = None) -> None:
    """Download a file from a URL."""
    import requests

    if local_path.exists() and not overwrite:
        raise FileExistsError(f"The file {local_path} already exists and overwrite is set to False.")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(local_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
    if chmod is not None:
        local_path.chmod(0o600)


def _download_ssh_keys(
    api_key: str,
    key_id: str = "",
    ssh_home: Union[str, Path] = "",
    ssh_key_name: str = "lightning_rsa",
    overwrite: bool = False,
) -> None:
    if not ssh_home:
        ssh_home = Path.home() / ".ssh"
    elif isinstance(ssh_home, str):
        ssh_home = Path(ssh_home)
    if not key_id:
        key_id = str(uuid.uuid4())

    path_key = ssh_home / ssh_key_name
    path_pub = ssh_home / f"{ssh_key_name}.pub"

    # todo: consider hitting the API to get the key pair directly instead of using wget
    _download_file(
        f"https://lightning.ai/setup/ssh-gen?t={api_key}&id={key_id}&machineName={platform.node()}",
        path_key,
        overwrite=overwrite,
        chmod=0o600,
    )
    _download_file(f"https://lightning.ai/setup/ssh-public?t={api_key}&id={key_id}", path_pub, overwrite=overwrite)
