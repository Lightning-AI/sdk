"""SSH generate command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.resource_completion import complete_studio
from lightning_sdk.cli.ssh.common import generate_ssh_config
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace


@click.command("generate", cls=LightningCommand)
@click.option(
    "--name",
    default=None,
    help="Studio to use. Falls back to the current Studio or configured default.",
    shell_complete=complete_studio,
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
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)
    conf = generate_ssh_config(key_path="~/.ssh/lightning_rsa", user=f"s_{studio._studio.id}", host=studio.name)
    Console().print(f"# ssh s_{studio._studio.id}@ssh.lightning.ai\n\n" + conf)
