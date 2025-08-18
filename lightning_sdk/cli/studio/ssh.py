"""Studio SSH command."""

from typing import Optional

import click


@click.command("ssh")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def ssh_studio(studio_name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """SSH into a Studio."""
    raise NotImplementedError("Not implemented")
