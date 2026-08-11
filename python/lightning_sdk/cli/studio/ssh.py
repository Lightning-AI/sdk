"""Studio SSH command."""

from typing import List, Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_studio, resolve_teamspace
from lightning_sdk.cli.utils.save_to_config import save_studio_to_config
from lightning_sdk.cli.utils.ssh_connection import _studio_ssh_user, exec_ssh


@click.command("ssh", cls=LightningCommand)
@click.option(
    "--name",
    help="Studio to use. Falls back to the current Studio or configured default.",
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
    return ssh_impl(name=name, teamspace=teamspace, option=option)


def ssh_impl(name: Optional[str], teamspace: Optional[str], option: Optional[List[str]]) -> None:
    resolved_teamspace = resolve_teamspace(teamspace)
    studio = resolve_studio(name, resolved_teamspace)
    save_studio_to_config(studio)

    ssh_user = _studio_ssh_user(studio._studio.id)
    extra_options = list(option) if option else []
    exec_ssh(ssh_user, extra_options=extra_options)
