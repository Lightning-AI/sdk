from typing import Optional, Tuple

from lightning_sdk.api.org_api import OrgApi
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.api.user_api import UserApi
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


class Studio:
    """A single Lightning AI Studio.

    Allows to fully control a studio, including retrieving the status, running commands
    and switching machine types.

    Args:
        name: the name of the studio
        teamspace: the name of the teamspace the studio is contained by
        org: the name of the organization owning the :param`teamspace` in case it is owned by an org
        user: the name of the user owning the :param`teamspace` in case it is owned directly by a user instead of an org
        cluster: the name of the cluster, the studio should be created on.
            Doesn't matter when the studio already exists.
        create_ok: whether the studio will be created if it does not yet exist. Defaults to True

    Note:
        Since a teamspace can either be owned by an org or by a user directly,
        only one of the arguments can be provided.

    """

    def __init__(
        self,
        name: str,
        teamspace: str,
        org: Optional[str] = None,
        user: Optional[str] = None,
        cluster: Optional[str] = None,
        create_ok: bool = True,
    ) -> None:
        self._studio_api = StudioApi()
        self._teamspace_api = TeamspaceApi()
        self._org_api = OrgApi()
        self._user_api = UserApi()

        self._org = org
        self._user = user
        self._cluster = cluster

        self._owner = None

        if org is not None and user is not None:
            raise ValueError(f"Only one of org and user can be provided, but got both: {org=} and {user=}.")

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
        except ValueError as e:
            if create_ok:
                self._studio = self._studio_api.create_studio(name, self._teamspace.id, cluster=self._cluster)
            else:
                raise ValueError(f"Studio {name} does not exist.") from e

    @property
    def name(self) -> str:
        """Returns the name of the studio."""
        return self._studio.name

    @property
    def status(self) -> Status:
        """Returns the Status of the Studio.

        Can be one of { NotCreated | Pending | Running | Stopping | Stopped | Failed }

        """
        internal_status = self._studio_api.get_studio_status(self._studio.id, self._teamspace.id).in_use
        return _internal_status_to_external_status(
            internal_status.phase if internal_status is not None else internal_status
        )

    @property
    def teamspace(self) -> str:
        """Returns the name of the Teamspace."""
        return self._teamspace.name

    @property
    def owner(self) -> str:
        """Returns the name of the owner (either user or org)."""
        return self._owner.name

    @property
    def machine(self) -> Optional[Machine]:
        """Returns the current machine type the Studio is running on."""
        if self.status != Status.Running:
            return None
        return self._studio_api.get_machine(self._studio.id, self._teamspace.id)

    def start(self) -> None:
        """Starts a Studio on the default machine type (CPU-4)."""
        status = self.status
        if status != Status.Stopped:
            raise RuntimeError(f"Cannot start a studio that is not stopped. Studio {self.name} is {status}.")
        self._studio_api.start_studio(self._studio.id, self._teamspace.id)

    def stop(self) -> None:
        """Stops a running Studio."""
        status = self.status
        if status not in (Status.Running, Status.Pending):
            raise RuntimeError(f"Cannot stop a studio that is not running. Studio {self.name} is {status}.")
        self._studio_api.stop_studio(self._studio.id, self._teamspace.id)

    def delete(self) -> None:
        """Deletes the current Studio."""
        self._studio_api.delete_studio(self._studio.id, self._teamspace.id)

    def duplicate(self) -> "Studio":
        """Duplicates the existing Studio to the same teamspace."""
        kwargs = self._studio_api.duplicate_studio(self._studio.id, self._teamspace._id, self._teamspace.id)
        return Studio(**kwargs)

    def switch_machine(self, machine: Machine) -> None:
        """Switches machine to the provied machine type/.

        Args:
            machine: the new machine type to switch to

        Note:
            this call is blocking until the new machine is provisioned

        """
        status = self.status
        if status != Status.Running:
            raise RuntimeError(
                f"Cannot switch machine on a studio that is not running. Studio {self.name} is {status}."
            )
        self._studio_api.switch_studio_machine(self._studio.id, self._teamspace.id, machine)

    def run_with_exit_code(self, *commands: str) -> Tuple[str, int]:
        """Runs given commands on the Studio while returning output and exit code.

        Args:
            commands: the commands to run on the Studio in sequence.

        """
        status = self.status
        if status != Status.Running:
            raise RuntimeError(f"Cannot run a command in a studio that is not running. Studio {self.name} is {status}.")
        output, exit_code = self._studio_api.run_studio_commands(self._studio.id, self._teamspace.id, *commands)
        output = output.strip()
        return output, exit_code

    def run(self, *commands: str) -> str:
        """Runs given commands on the Studio while returning only the output.

        Args:
            commands: the commands to run on the Studio in sequence.

        """
        output, exit_code = self.run_with_exit_code(*commands)
        if exit_code != 0:
            raise RuntimeError(output)
        return output

    def upload_file(self, filepath, remote_path: Optional[str] = None):
        import os
        if remote_path is None:
            remote_path = os.path.split(filepath)[1]

        self._studio_api.upload_file(self._studio.id, self._teamspace.id, self._studio.cluster_id, filepath, remote_path)


        
        


def _internal_status_to_external_status(internal_status: str) -> Status:
    """Converts internal status strings from HTTP requests to external enums."""
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

