"""Container list command."""

from typing import Optional

import click

from lightning_sdk.cli.legacy.list import containers as _list_containers


@click.command("list")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list containers from. Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
@click.option(
    "--cloud-account",
    "--cloud_account",
    default=None,
    help="The name of the cloud account where containers are stored in.",
)
def list_containers(teamspace: Optional[str] = None, cloud_account: Optional[str] = None) -> None:
    """Display the list of available containers."""
    _list_containers.callback(teamspace=teamspace, cloud_account=cloud_account)
