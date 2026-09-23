"""Machine list command."""

from typing import List, Optional, Tuple

import rich_click as click
from rich.console import Console
from rich.table import Table

from lightning_sdk import Machine
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.cli.utils.json_output import echo_json
from lightning_sdk.cli.utils.logging import LightningCommand
from lightning_sdk.cli.utils.resource_resolution import resolve_teamspace
from lightning_sdk.utils.resolve import _get_org_id

_TEAMSPACE_HELP = "Teamspace to list machines for, as 'owner/teamspace'. Falls back to your default teamspace."
_CATALOG_HELP = "List every machine the SDK knows about, instead of the ones your cloud account offers."


def _catalog_machines() -> List[Machine]:
    """Every machine the SDK knows about, regardless of what any cloud account offers."""
    return sorted(
        (m for m in vars(Machine).values() if isinstance(m, Machine) and m._include_in_cli),
        key=lambda m: m.name,
    )


def _account_machines(teamspace: Optional[str], cloud: Optional[str]) -> Tuple[List[Machine], str]:
    """The machines the resolved cloud account offers, with the account they came from."""
    resolved_teamspace = resolve_teamspace(teamspace)
    cloud_account = cloud or resolved_teamspace._teamspace_api._determine_cloud_account(resolved_teamspace.id)
    machines = StudioApi().supported_machines(
        teamspace_id=resolved_teamspace.id,
        cloud_account_id=cloud_account,
        org_id=_get_org_id(resolved_teamspace),
    )
    return sorted(machines, key=lambda m: m.name), cloud_account


@click.command("list", cls=LightningCommand)
@click.option("--teamspace", metavar="OWNER/NAME", help=_TEAMSPACE_HELP)
@click.option("--cloud", help="Cloud account to list machines for. Defaults to the teamspace's.")
@click.option("--catalog", is_flag=True, default=False, help=_CATALOG_HELP)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_machines(
    teamspace: Optional[str] = None,
    cloud: Optional[str] = None,
    catalog: bool = False,
    as_json: bool = False,
) -> None:
    """Display the machines you can start in your cloud account.

    A machine the account does not offer cannot be started, so this queries the account rather
    than listing every machine the SDK knows about. Pass --catalog for that full list.
    """
    if catalog:
        machines: List[Machine] = _catalog_machines()
        cloud_account: Optional[str] = None
    else:
        machines, cloud_account = _account_machines(teamspace, cloud)

    if as_json:
        echo_json(
            [
                {"name": m.name, "family": m.family, "count": m.accelerator_count, "cloud_account": cloud_account}
                for m in machines
            ]
        )
        return

    title = "Machines in the SDK catalog" if catalog else f"Machines available on {cloud_account}"
    table = Table(title=title, pad_edge=True)
    table.add_column("Name")
    table.add_column("Family")
    table.add_column("Count", justify="right")
    for machine in machines:
        table.add_row(machine.name, machine.family or "", str(machine.accelerator_count or ""))

    Console().print(table)
