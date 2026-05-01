"""MMT list command."""

from typing import Optional

import click


@click.command("list")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list multi-machine jobs from. Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
@click.option(
    "--all",
    is_flag=True,
    flag_value=True,
    default=False,
    help="if teamspace is not provided, list all multi-machine jobs in all teamspaces.",
)
@click.option(
    "--sort-by",
    "--sort_by",
    default=None,
    type=click.Choice(
        ["name", "teamspace", "studio", "image", "status", "machine", "cloud-account"], case_sensitive=False
    ),
    help="the attribute to sort the multi-machine jobs by.",
)
def list_mmts(teamspace: Optional[str] = None, all: bool = False, sort_by: Optional[str] = None) -> None:  # noqa: A002
    """List multi-machine jobs for a given teamspace."""
    from lightning_sdk.cli.legacy.list import mmts

    mmts.callback(teamspace=teamspace, all=all, sort_by=sort_by)
