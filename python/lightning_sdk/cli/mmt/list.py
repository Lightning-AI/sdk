"""MMT list command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("list", cls=LightningCommand)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list multi-machine jobs from. Should be specified as {owner}/{name}. "
        "Defaults to the configured teamspace."
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
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def list_mmts(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[str] = None,
    as_json: bool = False,
) -> None:
    """List multi-machine jobs for a given teamspace."""
    from lightning_sdk.cli.legacy.list import mmts

    callback = mmts.callback
    assert callback is not None
    callback(teamspace=teamspace, all=all, sort_by=sort_by, as_json=as_json)
