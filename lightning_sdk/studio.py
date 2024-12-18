import os
import warnings
from typing import TYPE_CHECKING, Any, Mapping, Optional, Tuple, Union

from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.utils import _machine_to_compute_name
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.machine import Machine
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.status import Status
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_deprecated_cluster, _resolve_teamspace, _setup_logger

if TYPE_CHECKING:
    from lightning_sdk.plugin import Plugin

_logger = _setup_logger(__name__)


class Studio:
    """A single Lightning AI Studio.

    Allows to fully control a studio, including retrieving the status, running commands
    and switching machine types.

    Args:
        name: the name of the studio
        teamspace: the name of the teamspace the studio is contained by
        org: the name of the organization owning the :param`teamspace` in case it is owned by an org
        user: the name of the user owning the :param`teamspace` in case it is owned directly by a user instead of an org
        cloud_account: the name of the cloud account, the studio should be created on.
            Doesn't matter when the studio already exists.
        create_ok: whether the studio will be created if it does not yet exist. Defaults to True
    Note:
        Since a teamspace can either be owned by an org or by a user directly,
        only one of the arguments can be provided.

    """

    # skips init of studio, only set when using this as a shell for names, ids etc.
    _skip_init = False

    def __init__(
        self,
        name: Optional[str] = None,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
        cloud_account: Optional[str] = None,
        create_ok: bool = True,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
    ) -> None:
        self._studio_api = StudioApi()

        self._teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        self._cloud_account = _resolve_deprecated_cluster(cloud_account, cluster)
        self._setup_done = False

        self._plugins = {}

        if name is None:
            studio_id = os.environ.get("LIGHTNING_CLOUD_SPACE_ID", None)
            if studio_id is None:
                raise ValueError("Cannot autodetect Studio. Either use the SDK from within a Studio or pass a name!")
            self._studio = self._studio_api.get_studio_by_id(studio_id=studio_id, teamspace_id=self._teamspace.id)
        else:
            try:
                self._studio = self._studio_api.get_studio(name, self._teamspace.id)
            except ValueError as e:
                if create_ok:
                    self._studio = self._studio_api.create_studio(
                        name, self._teamspace.id, cloud_account=self._cloud_account
                    )
                else:
                    raise ValueError(f"Studio {name} does not exist.") from e

        if (
            not self._skip_init
            and _internal_status_to_external_status(
                self._studio_api._get_studio_instance_status_from_object(self._studio)
            )
            == Status.Running
        ):
            self._setup()

    def _setup(self) -> None:
        """Installs all plugins that should be currently installed."""
        if self._setup_done:
            return

        # make sure all plugins that should be installed are actually installed
        all_installed_plugins = self._list_installed_plugins()
        available_plugins = self.available_plugins
        for k in all_installed_plugins:
            # check if plugin is available for user to prevent issues on duplication
            if k in available_plugins:
                self._add_plugin(k)

        self._studio_api.start_keeping_alive(teamspace_id=self._teamspace.id, studio_id=self._studio.id)
        self._setup_done = True

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
    def teamspace(self) -> Teamspace:
        """Returns the name of the Teamspace."""
        return self._teamspace

    @property
    def owner(self) -> Owner:
        """Returns the name of the owner (either user or org)."""
        return self.teamspace.owner

    @property
    def machine(self) -> Optional[Machine]:
        """Returns the current machine type the Studio is running on."""
        if self.status != Status.Running:
            return None
        return self._studio_api.get_machine(self._studio.id, self._teamspace.id)

    @property
    def interruptible(self) -> bool:
        """Returns whether the Studio is running on a interruptible instance."""
        if self.status != Status.Running:
            return None

        return self._studio_api.get_interruptible(self._studio.id, self._teamspace.id)

    @property
    def cluster(self) -> str:
        """Returns the cluster the Studio is running on."""
        warnings.warn("Studio.cluster is deprecated. Use Studio.cloud_account instead", DeprecationWarning)
        return self.cloud_account

    @property
    def cloud_account(self) -> str:
        return self._studio.cluster_id

    def start(self, machine: Union[Machine, str] = Machine.CPU, interruptible: bool = False) -> None:
        """Starts a Studio on the specified machine type (default: CPU-4)."""
        status = self.status
        if status == Status.Running:
            curr_machine = _machine_to_compute_name(self.machine) if self.machine is not None else None
            if curr_machine != _machine_to_compute_name(machine):
                raise RuntimeError(
                    f"Requested to start studio on {machine}, but studio is already running on {self.machine}."
                    " Consider switching instead!"
                )
            _logger.info(f"Studio {self.name} is already running")
            return

        if status != Status.Stopped:
            raise RuntimeError(f"Cannot start a studio that is not stopped. Studio {self.name} is {status}.")
        self._studio_api.start_studio(self._studio.id, self._teamspace.id, machine, interruptible=interruptible)

        self._setup()

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
        kwargs = self._studio_api.duplicate_studio(self._studio.id, self._teamspace.id, self._teamspace.id)
        return Studio(**kwargs)

    def switch_machine(self, machine: Union[Machine, str], interruptible: bool = False) -> None:
        """Switches machine to the provided machine type/.

        Args:
            machine: the new machine type to switch to
            interruptible: determines whether to switch to an interruptible instance

        Note:
            this call is blocking until the new machine is provisioned

        """
        status = self.status
        if status != Status.Running:
            raise RuntimeError(
                f"Cannot switch machine on a studio that is not running. Studio {self.name} is {status}."
            )
        self._studio_api.switch_studio_machine(
            self._studio.id, self._teamspace.id, machine, interruptible=interruptible
        )

    def run_with_exit_code(self, *commands: str) -> Tuple[str, int]:
        """Runs given commands on the Studio while returning output and exit code.

        Args:
            commands: the commands to run on the Studio in sequence.

        """
        if _LIGHTNING_DEBUG:
            print(f"Running {commands=}")

        status = self.status
        if status != Status.Running:
            raise RuntimeError(f"Cannot run a command in a studio that is not running. Studio {self.name} is {status}.")
        output, exit_code = self._studio_api.run_studio_commands(self._studio.id, self._teamspace.id, *commands)
        output = output.strip()

        if _LIGHTNING_DEBUG:
            print(f"Output {exit_code=} {output=}")

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

    def upload_file(self, file_path: str, remote_path: Optional[str] = None, progress_bar: bool = True) -> None:
        """Uploads a given file to a remote path on the Studio."""
        if remote_path is None:
            remote_path = os.path.split(file_path)[1]

        self._studio_api.upload_file(
            studio_id=self._studio.id,
            teamspace_id=self._teamspace.id,
            cloud_account=self._studio.cluster_id,
            file_path=file_path,
            remote_path=os.path.normpath(remote_path),
            progress_bar=progress_bar,
        )

    def download_file(self, remote_path: str, file_path: Optional[str] = None) -> None:
        """Downloads a file from the Studio to a given target path."""
        if file_path is None:
            file_path = remote_path

        self._studio_api.download_file(
            path=remote_path,
            target_path=file_path,
            studio_id=self._studio.id,
            teamspace_id=self._teamspace.id,
            cloud_account=self._studio.cluster_id,
        )

    def download_folder(self, remote_path: str, target_path: Optional[str] = None) -> None:
        """Downloads a folder from the Studio to a given target path."""
        if target_path is None:
            target_path = remote_path

        self._studio_api.download_folder(
            path=remote_path,
            target_path=target_path,
            studio_id=self._studio.id,
            teamspace_id=self._teamspace.id,
            cloud_account=self._studio.cluster_id,
        )

    @property
    def auto_sleep(self) -> bool:
        """Returns if a Studio has auto-sleep enabled."""
        return not self._studio.code_config.disable_auto_shutdown

    @auto_sleep.setter
    def auto_sleep(self, value: bool) -> None:
        if not value and self.machine == Machine.CPU:
            warnings.warn("Disabling auto-sleep will convert the Studio from free to paid!")
        self._studio_api.update_autoshutdown(self._studio.id, self._teamspace.id, enabled=value, studio=self._studio)
        self._update_studio_reference()

    @property
    def auto_sleep_time(self) -> int:
        """Returns the time in seconds a Studio has to be idle for auto-sleep to kick in (if enabled)."""
        return self._studio.code_config.idle_shutdown_seconds

    @auto_sleep_time.setter
    def auto_sleep_time(self, value: int) -> None:
        warnings.warn("Setting auto-sleep time will convert the Studio from free to paid!")
        self._studio_api.update_autoshutdown(
            self._studio.id, self._teamspace.id, idle_shutdown_seconds=value, studio=self._studio
        )
        self._update_studio_reference()

    @property
    def auto_shutdown(self) -> bool:
        warnings.warn("auto_shutdown is deprecated. Use auto_sleep instead", DeprecationWarning)
        return self.auto_sleep

    @auto_shutdown.setter
    def auto_shutdown(self, value: bool) -> None:
        warnings.warn("auto_shutdown is deprecated. Use auto_sleep instead", DeprecationWarning)
        self.auto_sleep = value

    @property
    def auto_shutdown_time(self) -> int:
        warnings.warn("auto_shutdown_time is deprecated. Use auto_sleep_time instead", DeprecationWarning)
        return self.auto_sleep_time

    @auto_shutdown_time.setter
    def auto_shutdown_time(self, value: int) -> None:
        warnings.warn("auto_shutdown_time is deprecated. Use auto_sleep_time instead", DeprecationWarning)
        self.auto_sleep_time = value

    @property
    def available_plugins(self) -> Mapping[str, str]:
        """All available plugins to install in the current Studio."""
        return self._studio_api.list_available_plugins(self._studio.id, self._teamspace.id)

    @property
    def installed_plugins(self) -> Mapping[str, "Plugin"]:
        """All plugins that are currently installed in this Studio."""
        return self._plugins

    def install_plugin(self, plugin_name: str) -> None:
        """Installs a given plugin to a Studio."""
        try:
            additional_info = self._studio_api.install_plugin(self._studio.id, self._teamspace.id, plugin_name)
        except RuntimeError as e:
            # reraise from here to avoid having api layer in traceback
            raise e

        if additional_info and self._setup_done:
            _logger.info(additional_info)

        self._add_plugin(plugin_name)

    def run_plugin(self, plugin_name: str, *args: Any, **kwargs: Any) -> str:
        """Runs a given plugin in a Studio."""
        return self._plugins[plugin_name].run(*args, **kwargs)

    def uninstall_plugin(self, plugin_name: str) -> None:
        """Uninstalls the given plugin from the Studio."""
        try:
            self._studio_api.uninstall_plugin(self._studio.id, self._teamspace.id, plugin_name)
        except RuntimeError as e:
            # reraise from here to avoid having api layer in traceback
            raise e

        self._plugins.pop(plugin_name)

    def _list_installed_plugins(self) -> Mapping[str, str]:
        """Lists all plugins that should be installed."""
        return self._studio_api.list_installed_plugins(self._studio.id, self._teamspace.id)

    def _add_plugin(self, plugin_name: str) -> None:
        """Adds the just installed plugin to the internal list of plugins."""
        from lightning_sdk.plugin import (
            InferenceServerPlugin,
            JobsPlugin,
            MultiMachineTrainingPlugin,
            Plugin,
        )

        if plugin_name in self._plugins:
            return

        plugin_cls = {
            "jobs": JobsPlugin,
            "multi-machine-training": MultiMachineTrainingPlugin,
            "inference-server": InferenceServerPlugin,
        }.get(plugin_name, Plugin)

        description = self._list_installed_plugins()[plugin_name]

        self._plugins[plugin_name] = plugin_cls(plugin_name, description, self)

    def _execute_plugin(self, plugin_name: str) -> Tuple[str, int]:
        """Executes a plugin command on the Studio."""
        output = self._studio_api.execute_plugin(self._studio.id, self._teamspace.id, plugin_name)
        _logger.info(output)
        return output

    def __eq__(self, other: "Studio") -> bool:
        """Checks for equality with other Studios."""
        return (
            isinstance(other, Studio)
            and self.name == other.name
            and self.teamspace == other.teamspace
            and self.owner == other.owner
        )

    def __repr__(self) -> str:
        """Returns reader friendly representation."""
        return f"Studio(name={self.name}, teamspace={self.teamspace!r})"

    def __str__(self) -> str:
        """Returns reader friendly representation."""
        return repr(self)

    def _update_studio_reference(self) -> None:
        self._studio = self._studio_api.get_studio_by_id(studio_id=self._studio.id, teamspace_id=self._teamspace.id)


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
