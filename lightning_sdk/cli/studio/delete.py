"""Studio delete command."""

from typing import Optional

import click


@click.command("delete")
@click.argument("studio_name", required=False)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
def delete_studio(studio_name: Optional[str] = None, teamspace: Optional[str] = None) -> None:
    """Delete a Studio."""
    raise NotImplementedError("Not implemented")
