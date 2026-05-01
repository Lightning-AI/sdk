"""SSH generate command."""

from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.legacy.studios_menu import _StudiosMenu
from lightning_sdk.cli.ssh.common import generate_ssh_config


@click.command("generate")
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
def generate_ssh(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Get SSH config entry for a studio."""
    menu = _StudiosMenu()
    studio = menu._get_studio(name=name, teamspace=teamspace)
    conf = generate_ssh_config(key_path="~/.ssh/lightning_rsa", user=f"s_{studio._studio.id}", host=studio.name)
    Console().print(f"# ssh s_{studio._studio.id}@ssh.lightning.ai\n\n" + conf)
