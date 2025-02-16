import subprocess
import sys
from typing import Optional

import click

from lightning_sdk.cli.configure import ssh as configure_ssh
from lightning_sdk.cli.studios_menu import _StudiosMenu


@click.group(name="connect")
def connect() -> None:
    """Connect to lightning products."""


@connect.command(name="studio")
@click.option("--name", default=None, help="The name of the studio to connect to.")
@click.option(
    "--teamspace",
    default=None,
    help="The teamspace the studio is part of. Should be of format <OWNER>/<TEAMSPACE_NAME>.",
)
def studio(name: Optional[str], teamspace: Optional[str]) -> None:
    """Connect to a studio via SSH."""
    configure_ssh(name=name, teamspace=teamspace, overwrite=False)

    menu = _StudiosMenu()
    studio = menu._get_studio(name=name, teamspace=teamspace)

    try:
        subprocess.run(["ssh", studio.name])
    except Exception as ex:
        print(f"Failed to establish SSH connection: {ex}")
        sys.exit(1)
