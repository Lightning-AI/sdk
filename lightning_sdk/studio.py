from typing import Optional

from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


class Studio:
    def __init__(
        self, name: str, teamspace: str, org: str, cluster: Optional[str] = None, create_ok: bool = True
    ) -> None:
        self._studio_api = StudioApi()
        self._teamspace_api = TeamspaceApi()
        self._org_api = OrgApi()

        self._org = self._org_api.get_org(org)
        self._teamspace = self._teamspace_api.get_teamspace(teamspace, self._org.id)
        self._studio = self._studio_api.get_studio(name, self._teamspace.id)

        if self._studio is None:
            if create_ok:
                self._studio = self._studio_api.create_studio(name, self._teamspace.id)
            else:
                raise ValueError(f"Studio {name} does not exist.")

    @property
    def status(self) -> Status:
        # TODO: convert the status from the API layer into a user facing status
        return self._studio_api.get_studio_status(self._studio.id, self._teamspace.id).in_use

    @property
    def teamspace(self) -> str:
        return self._teamspace.name

    @property
    def org(self) -> str:
        return self._org.name

    def start(self) -> None:
        self._studio_api.start_studio(self._studio.id, self._teamspace.id)

    def stop(self) -> None:
        self._studio_api.stop_studio(self._studio.id, self._teamspace.id)

    def delete(self) -> None:
        ...

    def duplicate(self) -> "Studio":
        ...

    def switch_machine(self, machine: Machine) -> None:
        self._studio_api.switch_studio_machine(self._studio.id, self._teamspace.id, machine)

    def run(self, *commands: str) -> str:
        return "".join(self._studio_api.run_studio_commands(self._studio.id, self._teamspace.id, *commands)).strip()
