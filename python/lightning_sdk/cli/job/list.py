"""Job list command."""

from typing import Optional

import rich_click as click

from lightning_sdk.cli.utils.logging import LightningCommand


@click.command("list", cls=LightningCommand)
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list jobs from. Should be specified as {owner}/{name} "
        "If not provided, can be selected in an interactive menu."
    ),
)
@click.option(
    "--all",
    is_flag=True,
    flag_value=True,
    default=False,
    help="if teamspace is not provided, list all jobs in all teamspaces.",
)
@click.option(
    "--sort-by",
    "--sort_by",
    default=None,
    type=click.Choice(
        ["name", "teamspace", "status", "studio", "machine", "image", "cloud-account"], case_sensitive=False
    ),
    help="the attribute to sort the jobs by.",
)
def list_jobs(teamspace: Optional[str] = None, all: bool = False, sort_by: Optional[str] = None) -> None:  # noqa: A002
    """List jobs for a given teamspace."""
    from lightning_sdk.cli.legacy.list import jobs

    jobs.callback(teamspace=teamspace, all=all, sort_by=sort_by)
