"""Studio list command."""

from typing import Callable, Optional

import click
from rich.table import Table

from lightning_sdk.cli.utils.cloud_account_map import cloud_account_to_display_name
from lightning_sdk.cli.utils.resolve import resolve_teamspace_owner_name_format
from lightning_sdk.cli.utils.richt_print import rich_to_str
from lightning_sdk.studio import Studio


@click.command("list")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--sort-by",
    default=None,
    type=click.Choice(["name", "teamspace", "status", "machine", "cloud-account"], case_sensitive=False),
    help="the attribute to sort the studios by.",
)
def list_studios(teamspace: Optional[str] = None, sort_by: Optional[str] = None) -> None:
    """List Studios in a teamspace.

    Example:
        lightning studio list --teamspace owner/teamspace

    """
    teamspace_resolved = resolve_teamspace_owner_name_format(teamspace)

    if teamspace_resolved is None:
        # TODO: make this a generic CLI error
        raise ValueError(f"Could not resolve teamspace: {teamspace}")

    studios = teamspace_resolved.studios

    table = Table(
        pad_edge=True,
    )
    table.add_column("Name")
    table.add_column("Teamspace")
    table.add_column("Status")
    table.add_column("Machine")
    table.add_column("Cloud account")

    for studio in sorted(studios, key=_sort_studios_key(sort_by)):
        table.add_row(
            studio.name,
            f"{studio.teamspace.owner.name}/{studio.teamspace.name}",
            str(studio.status),
            str(studio.machine) if studio.machine is not None else None,  # when None the cell is empty
            str(cloud_account_to_display_name(studio.cloud_account, studio.teamspace.id)),
        )

    click.echo(rich_to_str(table), color=True)


def _sort_studios_key(sort_by: str) -> Callable[[Studio], str]:
    """Return a key function to sort studios by a given attribute."""
    sort_key_map = {
        "name": lambda s: str(s.name or ""),
        "teamspace": lambda s: str(s.teamspace.name or ""),
        "status": lambda s: str(s.status or ""),
        "machine": lambda s: str(s.machine or ""),
        "cloud-account": lambda s: str(cloud_account_to_display_name(s.cloud_account or "", s.teamspace.id)),
    }
    return sort_key_map.get(sort_by, lambda s: s.name)
