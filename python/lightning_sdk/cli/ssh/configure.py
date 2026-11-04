"""SSH configure command."""

from typing import Optional

import rich_click as click
from rich.console import Console

from lightning_sdk.cli.resource_completion import complete_studio
from lightning_sdk.cli.ssh.common import add_ssh_config
from lightning_sdk.cli.utils.auth import require_auth_header
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace
from lightning_sdk.cli.utils.ssh_connection import ensure_ssh_key

OVERWRITE_HELP = "Deprecated, and has no effect: the SSH key is never replaced."
OVERWRITE_WARNING = (
    "--overwrite no longer replaces the SSH key. To make a new one, delete {key_path} and its .pub file, "
    "then run this again."
)


@click.command("configure", cls=LightningCommand)
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
@click.option(
    "--overwrite",
    is_flag=True,
    flag_value=True,
    default=False,
    help=OVERWRITE_HELP,
)
def configure_ssh(name: Optional[str] = None, teamspace: Optional[str] = None, overwrite: bool = False) -> None:
    """Get SSH config entry for a studio."""
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)

    require_auth_header()
    configure_studio_ssh(studio.name, f"s_{studio._studio.id}", overwrite=overwrite)


def configure_studio_ssh(host: str, user: str, overwrite: bool = False) -> None:
    """Set up this machine's SSH key and add the ``~/.ssh/config`` entry ``host`` for ``user``."""
    console = Console()
    key_path = ensure_ssh_key()
    if overwrite:
        console.print(OVERWRITE_WARNING.format(key_path=key_path), style="yellow")
    console.print(f"Using SSH key {key_path}")

    if add_ssh_config(host=host, user=user):
        console.print(f"Added {host} to ~/.ssh/config")
    else:
        console.print(f"~/.ssh/config already uses this key for {host}")
