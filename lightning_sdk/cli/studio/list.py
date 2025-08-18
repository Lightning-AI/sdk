"""Studio list command."""

from typing import Optional

import click


@click.command("list")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--sort-by",
    default=None,
    type=click.Choice(["name", "teamspace", "status", "machine", "cloud-account"], case_sensitive=False),
    help="the attribute to sort the studios by.",
)
def list_studios(teamspace: Optional[str] = None, sort_by: Optional[str] = None) -> None:
    """List Studios in the specified teamspace."""
    raise NotImplementedError("Not implemented")
