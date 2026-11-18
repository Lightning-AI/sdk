from typing import Optional

import click
from rich.console import Console

from lightning_sdk.cli.ssh.common import generate_ssh_config
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace


@click.group(name="generate")
def generate() -> None:
    """Generate configs (such as ssh for studio) and print them to commandline."""


@generate.command(name="ssh")
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
def ssh(name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Get SSH config entry for a studio."""
    studio = resolve_studio(name, resolve_teamspace(teamspace))

    conf = generate_ssh_config(user=f"s_{studio._studio.id}", host=studio.name)
    # Print the SSH config
    Console().print(f"# ssh s_{studio._studio.id}@ssh.lightning.ai\n\n" + conf)
