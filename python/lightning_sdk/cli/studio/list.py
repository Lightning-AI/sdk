"""Studio list command."""

from typing import Callable, Optional

import rich_click as click
from rich.table import Table

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.cli.utils.cloud_account_map import cloud_account_display_name_from_list
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

    # Fetched once and reused below -- refetching per Studio here is what made this command slow.
    global_cloud_accounts = CloudAccountApi().list_global_cloud_accounts(teamspace_id=teamspace_resolved.id)

    studios = sorted(
        filter(lambda s: all or s._studio.user_id == user.id, teamspace_resolved.studios),
        key=_sort_studios_key(sort_by, global_cloud_accounts),
    )

    if as_json:
        rows = []
        for studio in studios:
            with prevent_refetch_studio(studio):
                machine = studio.machine  # uncached property -- read once, not per branch below
                rows.append(
                    {
                        "name": studio.name,
                        "teamspace": f"{studio.teamspace.owner.name}/{studio.teamspace.name}",
                        "status": str(studio.status),
                        "machine": str(machine) if machine is not None else None,
                        "cloud_account": str(
                            cloud_account_display_name_from_list(studio.cloud_account, global_cloud_accounts)
                        ),
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
            machine = studio.machine  # uncached property -- read once, not per branch below
            table.add_row(
                # cannot convert to ascii here, as the final rich table has to be converted to ascii
                # otherwise the lack of support for linking in some terminals causes formatting issues.
                studio_name_link(studio, to_ascii=False),
                f"{studio.teamspace.owner.name}/{studio.teamspace.name}",
                str(studio.status),
                str(machine) if machine is not None else None,  # when None the cell is empty
                str(cloud_account_display_name_from_list(studio.cloud_account, global_cloud_accounts)),
            )

    click.echo(rich_to_str(table), color=True)


def _sort_studios_key(sort_by: str, global_cloud_accounts: list) -> Callable[[Studio], str]:
    """Return a key function to sort studios by a given attribute.

    Status/machine/cloud-account keys run under ``prevent_refetch_studio`` so sorting by one of them
    doesn't force a live per-Studio refetch ahead of the (already-cached) row-rendering pass below.
    """

    def _cached(s: Studio, attr: str) -> str:
        with prevent_refetch_studio(s):
            return str(getattr(s, attr) or "")

    sort_key_map = {
        "name": lambda s: str(s.name or ""),
        "teamspace": lambda s: str(s.teamspace.name or ""),
        "status": lambda s: _cached(s, "status"),
        "machine": lambda s: _cached(s, "machine"),
        "cloud-account": lambda s: cloud_account_display_name_from_list(s.cloud_account or "", global_cloud_accounts),
    }
    return sort_key_map.get(sort_by, lambda s: s.name)
