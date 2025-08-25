from contextlib import suppress
from typing import Callable, Optional

import click
from rich.console import Console
from rich.table import Table
from typing_extensions import Literal

from lightning_sdk import Job, Machine, Studio, Teamspace
from lightning_sdk.cli.legacy.clusters_menu import _ClustersMenu
from lightning_sdk.cli.utils.teamspace_selection import TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi import V1MultiMachineJob
from lightning_sdk.lit_container import LitContainer
from lightning_sdk.utils.resolve import _get_authed_user


@click.group(name="list")
def list_cli() -> None:
    """List resources on the Lightning AI platform."""


@list_cli.command(name="studios")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list studios from. Should be specified as {owner}/{name}"
        "If not provided, can be selected in an interactive menu."
    ),
)
@click.option(
    "--all",
    is_flag=True,
    flag_value=True,
    default=False,
    help="if teamspace is not provided, list all studios in all teamspaces.",
)
@click.option(
    "--sort-by",
    default=None,
    type=click.Choice(["name", "teamspace", "status", "machine", "cloud-account"], case_sensitive=False),
    help="the attribute to sort the studios by.",
)
def studios(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[Literal["name", "teamspace", "status", "machine", "cloud-account"]] = None,
) -> None:
    """List studios for a given teamspace."""
    studios = []
    menu = TeamspacesMenu()
    if all and not teamspace:
        user = _get_authed_user()
        possible_teamspaces = menu._get_possible_teamspaces(user)
        for ts in possible_teamspaces.values():
            teamspace = Teamspace(**ts)
            studios.extend(teamspace.studios)
    else:
        resolved_teamspace = menu(teamspace=teamspace)
        studios = resolved_teamspace.studios

    table = Table(
        pad_edge=True,
    )
    table.add_column("Name")
    table.add_column("Teamspace")
    table.add_column("Status")
    table.add_column("Machine")
    table.add_column("Cloud account")
    for studio in sorted(studios, key=_sort_studios_key(sort_by)):
        table.add_row(
            studio.name,
            f"{studio.teamspace.owner.name}/{studio.teamspace.name}",
            str(studio.status),
            str(studio.machine) if studio.machine is not None else None,  # when None the cell is empty
            str(studio.cloud_account),
        )

    Console().print(table)


@list_cli.command(name="jobs")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list jobs from. Should be specified as {owner}/{name}"
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
def jobs(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[Literal["name", "teamspace", "status", "studio", "machine", "image", "cloud-account"]] = None,
) -> None:
    """List jobs for a given teamspace."""
    jobs = []
    menu = TeamspacesMenu()
    if all and not teamspace:
        user = _get_authed_user()
        possible_teamspaces = menu._get_possible_teamspaces(user)
        for ts in possible_teamspaces.values():
            teamspace = Teamspace(**ts)
            jobs.extend(teamspace.jobs)
    else:
        resolved_teamspace = menu(teamspace=teamspace)
        jobs = resolved_teamspace.jobs

    table = Table(pad_edge=True)
    table.add_column("Name")
    table.add_column("Teamspace")
    table.add_column("Studio")
    table.add_column("Image")
    table.add_column("Status")
    table.add_column("Machine")
    table.add_column("Total Cost")
    for j in sorted(jobs, key=_sort_jobs_key(sort_by)):
        # we know we just fetched these, so no need to refetch
        j._prevent_refetch_latest = True
        j._internal_job._prevent_refetch_latest = True

        studio = j.studio
        with suppress(RuntimeError):
            table.add_row(
                j.name,
                f"{j.teamspace.owner.name}/{j.teamspace.name}",
                studio.name if studio else None,
                j.image,
                str(j.status) if j.status is not None else None,
                str(j.machine),
                f"{j.total_cost:.3f}",
            )

    Console().print(table)


@list_cli.command(name="mmts")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list multi-machine jobs from. Should be specified as {owner}/{name}"
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
def mmts(
    teamspace: Optional[str] = None,
    all: bool = False,  # noqa: A002
    sort_by: Optional[Literal["name", "teamspace", "studio", "image", "status", "machine", "cloud-account"]] = None,
) -> None:
    """List multi-machine jobs for a given teamspace."""
    jobs = []
    menu = TeamspacesMenu()
    if all and not teamspace:
        user = _get_authed_user()
        possible_teamspaces = menu._get_possible_teamspaces(user)
        for ts in possible_teamspaces.values():
            teamspace = Teamspace(**ts)
            jobs.extend(teamspace.multi_machine_jobs)
    else:
        resolved_teamspace = menu(teamspace=teamspace)
        jobs = resolved_teamspace.multi_machine_jobs

    table = Table(pad_edge=True)
    table.add_column("Name")
    table.add_column("Teamspace")
    table.add_column("Studio")
    table.add_column("Image")
    table.add_column("Status")
    table.add_column("Machine")
    table.add_column("Num Machines")
    table.add_column("Total Cost")
    for j in sorted(jobs, key=_sort_mmts_key(sort_by)):
        # we know we just fetched these, so no need to refetch
        j._prevent_refetch_latest = True
        with suppress(AttributeError):
            j._internal_job._prevent_refetch_latest = True

        studio = j.studio
        with suppress(RuntimeError):
            table.add_row(
                j.name,
                f"{j.teamspace.owner.name}/{j.teamspace.name}",
                studio.name if studio else None,
                j.image,
                str(j.status),
                str(j.machine),
                str(j.num_machines),
                str(j.total_cost),
            )

    Console().print(table)


@list_cli.command(name="containers")
@click.option(
    "--teamspace",
    default=None,
    help=(
        "the teamspace to list containers from. Should be specified as {owner}/{name}"
        "If not provided, can be selected in an interactive menu."
    ),
)
@click.option(
    "--cloud-account",
    "--cloud_account",  # The UI will present the above variant, using this as a secondary to be consistent w/ models
    default=None,
    help="The name of the cloud account where containers are stored in.",
)
def containers(teamspace: Optional[str] = None, cloud_account: Optional[str] = None) -> None:
    """Display the list of available containers."""
    api = LitContainer()
    menu = TeamspacesMenu()
    clusters_menu = _ClustersMenu()
    resolved_teamspace = menu(teamspace=teamspace)

    if not cloud_account:
        cloud_account = clusters_menu._resolve_cluster(resolved_teamspace)

    result = api.list_containers(
        teamspace=resolved_teamspace.name, org=resolved_teamspace.owner.name, cloud_account=cloud_account
    )

    if not result:
        return

    table = Table(pad_edge=True, box=None)
    table.add_column("REPOSITORY")
    table.add_column("CLOUD ACCOUNT")
    table.add_column("LATEST TAG")
    table.add_column("CREATED")
    for repo in result:
        table.add_row(repo["REPOSITORY"], repo["CLOUD ACCOUNT"], repo["LATEST TAG"], repo["CREATED"])
    Console().print(table)


@list_cli.command(name="machines")
def machines() -> None:
    """Display the list of available machines."""
    table = Table(pad_edge=True)
    table.add_column("Name")

    # Get all machine types from the enum
    machine_types = [
        name
        for name in dir(Machine)
        if isinstance(getattr(Machine, name), Machine) and getattr(Machine, name)._include_in_cli
    ]

    # Add rows to table
    for name in sorted(machine_types):
        table.add_row(name)

    Console().print(table)


def _sort_studios_key(sort_by: str) -> Callable[[Studio], str]:
    """Return a key function to sort studios by a given attribute."""
    sort_key_map = {
        "name": lambda s: str(s.name or ""),
        "teamspace": lambda s: str(s.teamspace.name or ""),
        "status": lambda s: str(s.status or ""),
        "machine": lambda s: str(s.machine or ""),
        "cloud-account": lambda s: str(s.cloud_account or ""),
    }
    return sort_key_map.get(sort_by, lambda s: s.name)


def _sort_jobs_key(sort_by: str) -> Callable[[Job], str]:
    """Return a key function to sort studios by a given attribute."""
    sort_key_map = {
        "name": lambda j: str(j.name or ""),
        "teamspace": lambda j: str(j.teamspace.name or ""),
        "status": lambda j: str(j.status or ""),
        "machine": lambda j: str(j.machine or ""),
        "studio": lambda j: str(j.studio or ""),
        "image": lambda j: str(j.image or ""),
        "cloud-account": lambda j: str(j.cloud_account or ""),
    }
    return sort_key_map.get(sort_by, lambda j: j.name)


def _sort_mmts_key(sort_by: str) -> Callable[[V1MultiMachineJob], str]:
    """Return a key function to sort multi-machine jobs by a given attribute."""
    sort_key_map = {
        "name": lambda j: str(j.name or ""),
        "teamspace": lambda j: str(j.teamspace.name or ""),
        "studio": lambda j: str(j.studio.name or ""),
        "image": lambda j: str(j.image or ""),
        "status": lambda j: str(j.status or ""),
        "machine": lambda j: str(j.machine or ""),
        "cloud-account": lambda j: str(j.cloud_account or ""),
    }
    return sort_key_map.get(sort_by, lambda j: j.name)
