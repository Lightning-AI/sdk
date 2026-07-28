"""Studio list command."""

from typing import Callable, Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.cli.utils.cloud_account_map import cloud_account_to_display_name
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.cli.utils.richt_print import rich_to_str, studio_name_link
from lightning_sdk.cli.utils.save_to_config import save_teamspace_to_config
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import _get_authed_user, prevent_refetch_studio


@click.command("list", cls=LightningCommand)
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--all",
    is_flag=True,
    flag_value=True,
    default=False,
    help="List all studios, not just the ones belonging to the authed user",
)
@click.option(
    "--sort-by",
    default=None,
    type=click.Choice(["name", "teamspace", "status", "machine", "cloud-account"], case_sensitive=False),
    help="the attribute to sort the studios by.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_studios(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[str] = None,
    as_json: bool = False,
) -> None:
    """List Studios in a teamspace.

    Example:
        lightning studio list --teamspace owner/teamspace

    """
    return list_impl(teamspace=teamspace, all=all, sort_by=sort_by, as_json=as_json)


def list_impl(teamspace: Optional[str], all: bool, sort_by: Optional[str], as_json: bool = False) -> None:  # noqa: A002
    teamspace_resolved = resolve_teamspace(teamspace)
    save_teamspace_to_config(teamspace_resolved, overwrite=False)

    user = _get_authed_user()

    studios = sorted(
        filter(lambda s: all or s._studio.user_id == user.id, teamspace_resolved.studios),
        key=_sort_studios_key(sort_by),
    )

    if as_json:
        rows = []
        for studio in studios:
            with prevent_refetch_studio(studio):
                rows.append(
                    {
                        "name": studio.name,
                        "teamspace": f"{studio.teamspace.owner.name}/{studio.teamspace.name}",
                        "status": str(studio.status),
                        "machine": str(studio.machine) if studio.machine is not None else None,
                        "cloud_account": str(cloud_account_to_display_name(studio.cloud_account, studio.teamspace.id)),
                    }
                )
        echo_json(rows)
        return

    table = Table(
        pad_edge=True,
    )
    table.add_column("Name")
    table.add_column("Teamspace")
    table.add_column("Status")
    table.add_column("Machine")
    table.add_column("Cloud account")

    for studio in studios:
        with prevent_refetch_studio(studio):
            table.add_row(
                # cannot convert to ascii here, as the final rich table has to be converted to ascii
                # otherwise the lack of support for linking in some terminals causes formatting issues.
                studio_name_link(studio, to_ascii=False),
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
