from typing import Optional

import click

from lightning_sdk.cli.ssh.configure import OVERWRITE_HELP, configure_studio_ssh
from lightning_sdk.cli.utils.auth import require_auth_header
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace


@click.group(name="configure")
def configure() -> None:
    """Configure access to resources on the Lightning AI platform."""


def _configure_ssh_internal(
    name: Optional[str] = None, teamspace: Optional[str] = None, overwrite: bool = False
) -> None:
    """Internal function to configure SSH without Click decorators."""
    require_auth_header()
    studio = resolve_studio(name, resolve_teamspace(teamspace))
    configure_studio_ssh(studio.name, f"s_{studio._studio.id}", overwrite=overwrite)


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
    help=OVERWRITE_HELP,
)
def ssh(name: Optional[str] = None, teamspace: Optional[str] = None, overwrite: bool = False) -> None:
    """Get SSH config entry for a studio."""
    _configure_ssh_internal(name=name, teamspace=teamspace, overwrite=overwrite)
