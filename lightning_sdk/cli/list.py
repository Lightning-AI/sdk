from contextlib import suppress
from typing import Callable, Optional

from rich.console import Console
from rich.table import Table
from typing_extensions import Literal

from lightning_sdk import Job, Machine, Studio, Teamspace
from lightning_sdk.cli.teamspace_menu import _TeamspacesMenu
from lightning_sdk.lightning_cloud.openapi import V1MultiMachineJob
from lightning_sdk.lit_container import LitContainer
from lightning_sdk.utils.resolve import _get_authed_user


class _List(_TeamspacesMenu):
    """List resources on the Lightning AI platform."""

    @staticmethod
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

    def studios(
        self,
        teamspace: Optional[str] = None,
        all: bool = False,  # noqa: A002
        sort_by: Optional[Literal["name", "teamspace", "status", "machine", "cloud-account"]] = None,
    ) -> None:
        """List studios for a given teamspace.

        Args:
            teamspace: the teamspace to list studios from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
            all: if teamspece is not provided, list all studios in all teamspaces.
            sort_by: the attribute to sort the studios by.
                Can be one of "name", "teamspace", "status", "machine", "cloud-account".

        """
        studios = []
        if all and not teamspace:
            user = _get_authed_user()
            possible_teamspaces = self._get_possible_teamspaces(user)
            for ts in possible_teamspaces.values():
                teamspace = Teamspace(**ts)
                studios.extend(teamspace.studios)
        else:
            resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)
            studios = resolved_teamspace.studios

        table = Table(
            pad_edge=True,
        )
        table.add_column("Name")
        table.add_column("Teamspace")
        table.add_column("Status")
        table.add_column("Machine")
        table.add_column("Cloud account")
        for studio in sorted(studios, key=self._sort_studios_key(sort_by)):
            table.add_row(
                studio.name,
                f"{studio.teamspace.owner.name}/{studio.teamspace.name}",
                str(studio.status),
                str(studio.machine) if studio.machine is not None else None,  # when None the cell is empty
                str(studio.cloud_account),
            )

        Console().print(table)

    @staticmethod
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

    def jobs(
        self,
        teamspace: Optional[str] = None,
        all: bool = False,  # noqa: A002
        sort_by: Optional[Literal["name", "teamspace", "status", "studio", "machine", "image", "cloud-account"]] = None,
    ) -> None:
        """List jobs for a given teamspace.

        Args:
            teamspace: the teamspace to list jobs from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
            all: if teamspece is not provided, list all jobs in all teamspaces.
            sort_by: the attribute to sort the jobs by.
                Can be one of "name", "teamspace", "status", "studio", "machine", "image", "cloud-account".

        """
        jobs = []
        if all and not teamspace:
            user = _get_authed_user()
            possible_teamspaces = self._get_possible_teamspaces(user)
            for ts in possible_teamspaces.values():
                teamspace = Teamspace(**ts)
                jobs.extend(teamspace.jobs)
        else:
            resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)
            jobs = resolved_teamspace.jobs

        table = Table(pad_edge=True)
        table.add_column("Name")
        table.add_column("Teamspace")
        table.add_column("Studio")
        table.add_column("Image")
        table.add_column("Status")
        table.add_column("Machine")
        table.add_column("Total Cost")
        for j in sorted(jobs, key=self._sort_jobs_key(sort_by)):
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

    def _sort_mmts_key(self, sort_by: str) -> Callable[[V1MultiMachineJob], str]:
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

    def mmts(
        self,
        teamspace: Optional[str] = None,
        all: bool = False,  # noqa: A002
        sort_by: Optional[Literal["name", "teamspace", "studio", "image", "status", "machine", "cloud-account"]] = None,
    ) -> None:
        """List multi-machine jobs for a given teamspace.

        Args:
            teamspace: the teamspace to list jobs from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
            all: if teamspece is not provided, list all multi-machine jobs in all teamspaces.
            sort_by: the attribute to sort the multi-machine jobs by.
                Can be one of "name", "teamspace", "studio", "image", "status", "machine", "cloud-account".

        """
        jobs = []
        if all and not teamspace:
            user = _get_authed_user()
            possible_teamspaces = self._get_possible_teamspaces(user)
            for ts in possible_teamspaces.values():
                teamspace = Teamspace(**ts)
                jobs.extend(teamspace.multi_machine_jobs)
        else:
            resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)
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
        for j in sorted(jobs, key=self._sort_mmts_key(sort_by)):
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

    def containers(self, teamspace: Optional[str] = None) -> None:
        """Display the list of available containers.

        Args:
            teamspace: The teamspace to list containers from. Should be specified as {owner}/{name}
                If not provided, can be selected in an interactive menu.
        """
        api = LitContainer()
        resolved_teamspace = self._resolve_teamspace(teamspace=teamspace)
        result = api.list_containers(teamspace=resolved_teamspace.name, org=resolved_teamspace.owner.name)
        table = Table(pad_edge=True, box=None)
        table.add_column("REPOSITORY")
        table.add_column("IMAGE ID")
        table.add_column("CREATED")
        for repo in result:
            table.add_row(repo["REPOSITORY"], repo["IMAGE ID"], repo["CREATED"])
        Console().print(table)

    def machines(self) -> None:
        """Display the list of available machines."""
        table = Table(pad_edge=True)
        table.add_column("Name")

        # Get all machine types from the enum
        machine_types = [name for name in dir(Machine) if not name.startswith("_")]

        # Add rows to table
        for name in sorted(machine_types):
            table.add_row(name)

        Console().print(table)
