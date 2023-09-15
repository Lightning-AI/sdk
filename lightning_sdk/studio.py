from typing import Optional
from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.api.user_api import UserApi
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


class Studio:
    def __init__(
        self, name: str, teamspace: str, org: Optional[str] = None, user: Optional[str] = None, cluster: Optional[str] = None, create_ok: bool = True
    ) -> None:
        self._studio_api = StudioApi()
        self._teamspace_api = TeamspaceApi()
        self._org_api = OrgApi()
        self._user_api = UserApi()

        self._org = org
        self._user = user

        self._owner = None

        if org:
            self._org = self._org_api.get_org(org)
            self._owner = self._org
        else:
            self._org = None

        if user:
            self._user = self._user_api.get_user(user)
            self._owner = self._user
        else:
            self._user = None

        if self._owner is None:
            raise RuntimeError(f"Could not find studio owner {org=}, {user=}")

        self._teamspace = self._teamspace_api.get_teamspace(teamspace, self._owner.id, is_user=self._org is None)
        
        try:
            self._studio = self._studio_api.get_studio(name, self._teamspace.id)
        except ValueError:
            if create_ok:
                self._studio = self._studio_api.create_studio(name, self._teamspace.id)
            else:
                raise ValueError(f"Studio {name} does not exist.")

    @property
    def name(self) -> str:
        return self._studio.name

    @property
    def status(self) -> Status:
        internal_status = self._studio_api.get_studio_status(self._studio.id, self._teamspace.id).in_use
        return _internal_status_to_external_status(
            internal_status.phase if internal_status is not None else internal_status
        )

    @property
    def teamspace(self) -> str:
        return self._teamspace.name

    @property
    def owner(self) -> str:
        return self._owner.name

    @property
    def machine(self) -> Optional[Machine]:
        if self.status != Status.Running:
            return None
        return self._studio_api.get_machine(self._studio.id, self._teamspace.id)

    def start(self) -> None:
        status = self.status
        if status != Status.Stopped:
            raise RuntimeError(f"Cannot start a studio that is not stopped. Studio {self.name} is {status}.")
        self._studio_api.start_studio(self._studio.id, self._teamspace.id)

    def stop(self) -> None:
        status = self.status
        if status not in (Status.Running, Status.Pending):
            raise RuntimeError(f"Cannot stop a studio that is not running. Studio {self.name} is {status}.")
        self._studio_api.stop_studio(self._studio.id, self._teamspace.id)

    def delete(self) -> None:
        self._studio_api.delete_studio(self._studio.id, self._teamspace.id)

    def duplicate(self) -> "Studio":
        raise NotImplementedError("Message us on Discord or Slack to request this feature!")

    def switch_machine(self, machine: Machine) -> None:
        status = self.status
        if status != Status.Running:
            raise RuntimeError(
                f"Cannot switch machine on a studio that is not running. Studio {self.name} is {status}."
            )
        self._studio_api.switch_studio_machine(self._studio.id, self._teamspace.id, machine)

    def run(self, *commands: str) -> str:
        status = self.status
        if status != Status.Running:
            raise RuntimeError(f"Cannot run a command in a studio that is not running. Studio {self.name} is {status}.")
        return "".join(self._studio_api.run_studio_commands(self._studio.id, self._teamspace.id, *commands)).strip()


def _internal_status_to_external_status(internal_status: str):
    return {
        # don't get a status if no instance alive
        None: Status.Stopped,
        # TODO: should unspecified resolve to pending?
        "CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED": Status.Pending,
        "CLOUD_SPACE_INSTANCE_STATE_PENDING": Status.Pending,
        "CLOUD_SPACE_INSTANCE_STATE_RUNNING": Status.Running,
        "CLOUD_SPACE_INSTANCE_STATE_FAILED": Status.Failed,
        "CLOUD_SPACE_INSTANCE_STATE_STOPPING": Status.Stopping,
        "CLOUD_SPACE_INSTANCE_STATE_STOPPED": Status.Stopped,
    }[internal_status]
