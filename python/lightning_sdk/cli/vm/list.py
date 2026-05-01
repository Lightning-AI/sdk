from typing import Optional

import click

from lightning_sdk.cli.studio.list import list_impl


@click.command("list")
@click.option("--teamspace", help="Override default teamspace (format: owner/teamspace)")
@click.option(
    "--all",
    is_flag=True,
    flag_value=True,
    default=False,
    help="List all VMs, not just the ones belonging to the authed user",
)
@click.option(
    "--sort-by",
    default=None,
    type=click.Choice(["name", "teamspace", "status", "machine", "cloud-account"], case_sensitive=False),
    help="the attribute to sort the VMs by.",
)
def list_vms(teamspace: Optional[str] = None, all: bool = False, sort_by: Optional[str] = None) -> None:  # noqa: A002
    """List VMs in a teamspace.

    Example:
        lightning vm list --teamspace owner/teamspace

    """
    return list_impl(teamspace=teamspace, all=all, sort_by=sort_by, vm=True)
