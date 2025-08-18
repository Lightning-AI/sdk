"""Studio stop command."""

from typing import Optional

import click


@click.command("stop")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def stop_studio(studio_name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Stop a Studio."""
    raise NotImplementedError("Not implemented")
