"""Teamspace list command."""

from functools import partial
from typing import Dict, List, Optional, Sequence

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk.api import OrgApi, UserApi
from lightning_sdk.cli.resource_completion import _configured_teamspace
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.list_filters import matches_filters, resolve_filters
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.lightning_cloud.openapi.models import V1Membership, V1OwnerType

# The keys `--sort-by` and `--filter` both accept; each must resolve to a row field via `_ROW_KEYS`.
LIST_KEYS = ("teamspace", "owner", "name", "owner-type", "display-name")

# Keys whose row field is named differently from the key itself.
_ROW_KEYS = {"owner-type": "owner_type", "display-name": "display_name"}


@click.command("list", cls=LightningCommand)
@click.option(
    "--sort-by",
    "--sort_by",
    default=None,
    type=click.Choice(list(LIST_KEYS), case_sensitive=False),
    help="the attribute to sort the teamspaces by.",
)
@click.option(
    "--filter",
    "filters",
    default=(),
    multiple=True,
    metavar="KEY=PATTERN",
    help=(
        "Only list teamspaces whose KEY matches PATTERN, a case-insensitive glob. Can be a comma-separated list "
        "or passed multiple times, and every filter has to match. "
        f"KEY is one of: {', '.join(LIST_KEYS)}."
    ),
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_teamspaces(sort_by: Optional[str] = None, filters: Sequence[str] = (), as_json: bool = False) -> None:
    """List the teamspaces you are a member of.

    The TEAMSPACE column is the owner/teamspace name that --teamspace accepts. The configured teamspace
    is marked as current.

    Example:
        lightning teamspace list
        lightning teamspace list --filter 'owner-type=organization' --sort-by owner
        lightning teamspace list --json

    """
    wanted_filters = resolve_filters(filters, LIST_KEYS)

    rows = [row for row in _teamspace_rows() if matches_filters(partial(_display, row), wanted_filters)]
    sort_by = (sort_by or "teamspace").lower()
    sort_key = _ROW_KEYS.get(sort_by, sort_by)
    rows.sort(key=lambda row: (str(row[sort_key] or "").lower(), str(row["teamspace"]).lower()))

    if as_json:
        echo_json(rows)
        return

    table = Table(pad_edge=True)
    for column in ("Teamspace", "Owner Type", "Display Name", "Current"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            str(row["teamspace"]),
            str(row["owner_type"]),
            str(row["display_name"] or ""),
            "*" if row["current"] else "",
        )
    Console().print(table)


def _teamspace_rows() -> List[Dict[str, object]]:
    """One row per membership, with its owner id resolved to the owner's name."""
    user_api = UserApi()
    memberships = user_api._get_all_teamspace_memberships("")
    owner_names = {org.id: org.name for org in user_api._get_organizations_for_authed_user()}

    rows: List[Dict[str, object]] = []
    for membership in memberships:
        owner = _owner_name(membership, owner_names, user_api)
        rows.append(
            {
                "teamspace": f"{owner}/{membership.name}",
                "owner": owner,
                "name": membership.name,
                "owner_type": str(membership.owner_type),
                "display_name": membership.display_name or "",
                "current": False,
            }
        )

    current = _current_teamspace(rows)
    for row in rows:
        row["current"] = row["teamspace"] == current
    return rows


def _owner_name(membership: V1Membership, owner_names: Dict[str, str], user_api: UserApi) -> str:
    """Resolve and cache a membership's owner name; orgs come preloaded, users are looked up once each."""
    owner_id = membership.owner_id
    if owner_id not in owner_names:
        if membership.owner_type == V1OwnerType.ORGANIZATION:
            owner_names[owner_id] = OrgApi()._get_org_by_id(owner_id).name
        else:
            owner_names[owner_id] = user_api._get_user_by_id(owner_id).username
    return owner_names[owner_id]


def _current_teamspace(rows: List[Dict[str, object]]) -> Optional[str]:
    """The listed owner/teamspace the configured teamspace points to, if any."""
    configured = _configured_teamspace()
    if not configured:
        return None
    if "/" in configured:
        matches = [row["teamspace"] for row in rows if str(row["teamspace"]).lower() == configured.lower()]
    else:
        # A bare name only identifies a teamspace when no two owners share it.
        matches = [row["teamspace"] for row in rows if row["name"] == configured]
    return str(matches[0]) if len(matches) == 1 else None


def _display(row: Dict[str, object], key: str) -> str:
    return str(row[_ROW_KEYS.get(key, key)] or "")
