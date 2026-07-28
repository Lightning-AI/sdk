"""Container list command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.legacy.list import containers as _list_containers
from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("list", cls=LightningCommand)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list containers from. Should be specified as {owner}/{name}. "
        "Defaults to the configured teamspace."
    ),
)
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help="The name of the cloud account where containers are stored in.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_containers(
    teamspace: Optional[str] = None, cloud_account: Optional[str] = None, as_json: bool = False
) -> None:
    """Display the list of available containers."""
    _list_containers.callback(teamspace=teamspace, cloud_account=cloud_account, as_json=as_json)
