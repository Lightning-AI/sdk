import glob
import os
import threading
import warnings
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Tuple, Union

from tqdm.auto import tqdm

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.constants import _LIGHTNING_DEBUG
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.status import Status
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.names import random_unique_name
from lightning_sdk.utils.resolve import (
    _get_org_id,
    _resolve_deprecated_cluster,
    _resolve_deprecated_provider,
    _resolve_teamspace,
    _setup_logger,
)

if TYPE_CHECKING:
    from lightning_sdk.job import Job
    from lightning_sdk.mmt import MMT
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
        cloud_account_provider: The provider to select the cloud-account from.
            If set, must be in agreement with the provider from the cloud_account (if specified).
            If not specified, falls backto the teamspace default cloud account.
        create_ok: whether the studio will be created if it does not yet exist. Defaults to True
        provider: the provider of the machine, the studio should be created on.

    Note:
        Since a teamspace can either be owned by an org or by a user directly,
        only one of the arguments can be provided.

    """

    # skips init of studio, only set when using this as a shell for names, ids etc.
    _skip_init = threading.local()
    _skip_setup = threading.local()

    # whether to show progress bars during operations
    show_progress = False

    def __init__(
        self,
        name: Optional[str] = None,
        teamspace: Optional[Union[str, Teamspace]] = None,
        org: Optional[Union[str, Organization]] = None,
        user: Optional[Union[str, User]] = None,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union[CloudProvider, str]] = None,
        create_ok: bool = True,
        cluster: Optional[str] = None,  # deprecated in favor of cloud_account
        source: Optional[str] = None,
        disable_secrets: bool = False,
        provider: Optional[Union[CloudProvider, str]] = None,  # deprecated in favor of cloud_provider
    ) -> None:
        self._studio_api = StudioApi()
        self._cloud_account_api = CloudAccountApi()

        self._prevent_refetch = False
        self._teamspace = None

        # don't resolve anything if we're skipping init
        if not getattr(self._skip_init, "value", False):
            _teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
            if _teamspace is None:
                raise ValueError("Couldn't resolve teamspace from the provided name, org, or user")

            self._teamspace = _teamspace

        self._setup_done = getattr(self._skip_setup, "value", False)
        self._disable_secrets = disable_secrets

        self._plugins = {}
        self._studio = None

        cloud_account = _resolve_deprecated_cluster(cloud_account, cluster)
        cloud_provider = _resolve_deprecated_provider(cloud_provider, provider)

        # if we're skipping init, we don't need to resolve the cloud account as then we're not creating a studio
        if self._teamspace is not None:
            _cloud_account = self._cloud_account_api.resolve_cloud_account(
                self._teamspace.id,
                cloud_account=cloud_account,
                cloud_provider=cloud_provider,
                default_cloud_account=self._teamspace.default_cloud_account,
            )

        # Resolve studio name if not provided: explicit → env (LIGHTNING_CLOUD_SPACE_ID) → config defaults
        if name is None and not getattr(self._skip_init, "value", False):
            studio_id = os.environ.get("LIGHTNING_CLOUD_SPACE_ID", None)
            if studio_id is not None:
                # We're inside a studio, get it by ID
                self._studio = self._studio_api.get_studio_by_id(studio_id=studio_id, teamspace_id=self._teamspace.id)
                name = self._studio.name
            else:
                # Try config defaults
                from lightning_sdk.utils.config import Config, DefaultConfigKeys

                config = Config()
                name = config.get_value(DefaultConfigKeys.studio)
                if name is None and not create_ok:
                    raise ValueError(
                        "Cannot autodetect Studio. Either use the SDK from within a Studio or pass a name!"
                    )

        if self._studio is None and not getattr(self._skip_init, "value", False):
            # If we have a name (explicit or from config), get studio by name
            try:
                if name is None:
                    # if we don't have a name, raise an error to get
                    # to the exception path and optionally create a studio
                    raise ValueError(
                        "Cannot autodetect Studio. Either use the SDK from within a Studio or pass a name!"
                    )
                self._studio = self._studio_api.get_studio(name, self._teamspace.id)
            except ValueError as e:
                if create_ok:
                    name = name or random_unique_name()
                    self._studio = self._studio_api.create_studio(
                        name,
                        self._teamspace.id,
                        cloud_account=_cloud_account,
                        source=source,
                        disable_secrets=self._disable_secrets,
                    )
                else:
                    raise e

        if (
            not getattr(self._skip_init, "value", False)
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
        return self._studio_api.get_machine(
            self._studio.id,
            self._teamspace.id,
            self.cloud_account,
            _get_org_id(self._teamspace),
        )

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

    def start(
        self,
        machine: Union[Machine, str] = Machine.CPU,
        interruptible: Optional[bool] = None,
        max_runtime: Optional[int] = None,
    ) -> None:
        """Starts a Studio on the specified machine type (default: CPU-4).

        Args:
            machine: the machine type to start the studio on. Defaults to CPU-4
            interruptible: whether to use interruptible machines
            max_runtime: the duration (in seconds) for which to allocate the machine.
                Irrelevant for most machines, required for some of the top-end machines on GCP.
                If in doubt, set it. Won't have an effect on machines not requiring it.
                Defaults to 3h

        """
        status = self.status

        if interruptible is None:
            interruptible_override = os.environ.get("LIGHTNING_INTERRUPTIBLE_OVERRIDE", None)
            if interruptible_override is not None:
                interruptible = interruptible_override.lower() == "true"
            else:
                interruptible = self.teamspace.start_studios_on_interruptible

        if status == Status.Running:
            new_machine = machine
            if not isinstance(machine, Machine):
                new_machine = Machine.from_str(machine)
            if new_machine != self.machine:
                raise RuntimeError(
                    f"Requested to start studio on {new_machine}, but studio is already running on {self.machine}."
                    " Consider switching instead!"
                )
            _logger.info(f"Studio {self.name} is already running")
            return

        if status != Status.Stopped:
            raise RuntimeError(f"Cannot start a studio that is not stopped. Studio {self.name} is {status}.")

        # Show progress bar during startup
        if self.show_progress:
            from lightning_sdk.utils.progress import StudioProgressTracker

            with StudioProgressTracker("start", show_progress=True) as progress:
                # Start the studio without blocking
                self._studio_api.start_studio_async(
                    self._studio.id, self._teamspace.id, machine, interruptible=interruptible, max_runtime=max_runtime
                )

                # Track progress through completion
                progress.track_startup_phases(
                    lambda: self._studio_api.get_studio_status(self._studio.id, self._teamspace.id)
                )
        else:
            # Use the blocking version if no progress is needed
            self._studio_api.start_studio(
                self._studio.id, self._teamspace.id, machine, interruptible=interruptible, max_runtime=max_runtime
            )

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

    def duplicate(
        self, target_teamspace: Optional[Union["Teamspace", str]] = None, machine: Machine = Machine.CPU
    ) -> "Studio":
        """Duplicates the existing Studio.

        Args:
            target_teamspace: the teamspace to duplicate the studio to.
                Must have the same owner as the source teamspace.
                If not provided, defaults to current teamspace.
            machine: the machine to start the duplicated studio on.
                Defaults to CPU
        """
        if target_teamspace is None:
            target_teamspace_id = self._teamspace.id
        else:
            target_teamspace = _resolve_teamspace(
                target_teamspace,
                org=self._teamspace.owner if isinstance(self._teamspace.owner, Organization) else None,
                user=self._teamspace.owner if isinstance(self._teamspace.owner, User) else None,
            )

            if target_teamspace is None:
                raise ValueError(
                    f"Could not resolve target teamspace {target_teamspace} "
                    f"with owner {self.teamspace.owner} for duplication!"
                )

            target_teamspace_id = target_teamspace.id

        kwargs = self._studio_api.duplicate_studio(
            studio_id=self._studio.id,
            teamspace_id=self._teamspace.id,
            target_teamspace_id=target_teamspace_id,
            machine=machine,
        )
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

        if self.show_progress:
            from lightning_sdk.utils.progress import StudioProgressTracker

            with StudioProgressTracker("switch", show_progress=True) as progress:
                # Update progress before starting the switch
                progress.update_progress(5, "Initiating machine switch...")

                # Start the switch operation with progress tracking
                self._studio_api.switch_studio_machine_with_progress(
                    self._studio.id, self._teamspace.id, machine, interruptible=interruptible, progress=progress
                )
        else:
            self._studio_api.switch_studio_machine(
                self._studio.id, self._teamspace.id, machine, interruptible=interruptible
            )

    def run_and_detach(self, *commands: str, timeout: float = 10, check_interval: float = 1) -> str:
        """Runs given commands on the Studio and returns immediately.

        The command will continue to run in the background.

        Args:
            timeout: wait for this many seconds for the command to finish.
            check_interval: check the status of the command every this many seconds.
        """
        if check_interval > timeout:
            raise ValueError("check_interval must be less than timeout")

        if _LIGHTNING_DEBUG:
            print(f"Running {commands=}")
        status = self.status
        if status != Status.Running:
            raise RuntimeError(f"Cannot run a command in a studio that is not running. Studio {self.name} is {status}.")

        iter_output = self._studio_api.run_studio_commands_and_yield(
            self._studio.id, self._teamspace.id, *commands, timeout=timeout, check_interval=check_interval
        )

        output = ""
        code = None
        for line, exit_code in iter_output:
            print(line)
            output += line
            code = exit_code
        return output, code

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

    def upload_folder(self, folder_path: str, remote_path: Optional[str] = None, progress_bar: bool = True) -> None:
        """Uploads a given folder to a remote path on the Studio."""
        if folder_path is None:
            raise ValueError("Cannot upload a folder that is None.")
        folder_path = os.path.normpath(folder_path)
        if os.path.isfile(folder_path):
            raise NotADirectoryError(f"Cannot upload a file as a folder. '{folder_path}' is a file.")
        if not os.path.exists(folder_path):
            raise NotADirectoryError(f"Cannot upload a folder that does not exist. '{folder_path}' is not a directory.")
        all_files = []
        for fp in glob.glob(os.path.join(folder_path, "**"), recursive=True):
            if not os.path.isfile(fp):
                continue
            rel_path = os.path.relpath(fp, folder_path)
            remote_file = os.path.join(remote_path, rel_path) if remote_path else rel_path
            all_files.append((fp, remote_file))

        if progress_bar:
            progress_bar = tqdm(total=len(all_files), desc="Uploading files", unit="file")
        for local_file, remote_path in sorted(all_files, key=lambda p: p[1]):
            if progress_bar:
                progress_bar.set_description(f"Uploading {local_file}")
            self.upload_file(local_file, remote_path=remote_path, progress_bar=False)
            if progress_bar:
                progress_bar.update(1)
        if progress_bar:
            progress_bar.close()

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

    def run_job(
        self,
        name: str,
        machine: Union["Machine", str],
        command: str,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
    ) -> "Job":
        """Run async workloads using the compute environment from your studio.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            command: The command to run inside your job.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
        """
        from lightning_sdk.job import Job

        return Job.run(
            name=name,
            machine=machine,
            command=command,
            studio=self,
            image=None,
            teamspace=self.teamspace,
            cloud_account=self.cloud_account,
            env=env,
            interruptible=interruptible,
        )

    def run_mmt(
        self,
        name: str,
        num_machines: int,
        machine: Union["Machine", str],
        command: str,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
    ) -> "MMT":
        """Run async workloads using the compute environment from your studio.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            num_machines: The number of machines to run on.
            machine: The machine type to run the job on. One of {", ".join(_MACHINE_VALUES)}.
            command: The command to run inside your job.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. They are cheaper but can be preempted.
        """
        from lightning_sdk.mmt import MMT

        return MMT.run(
            name=name,
            num_machines=num_machines,
            machine=machine,
            command=command,
            studio=self,
            image=None,
            teamspace=self.teamspace,
            cloud_account=self.cloud_account,
            env=env,
            interruptible=interruptible,
        )

    def create_assistant(self, name: str, port: int) -> None:
        assistant = self._studio_api.create_assistant(
            studio_id=self._studio.id, teamspace_id=self._teamspace.id, port=port, assistant_name=name
        )
        assistant_info = f"Created assisant with name: {assistant.name}, ID: {assistant.id}"
        self._assistant_id = assistant.id
        _logger.info(assistant_info)

    @property
    def auto_sleep(self) -> bool:
        """Returns if a Studio has auto-sleep enabled."""
        return not self._studio.code_config.disable_auto_shutdown

    @auto_sleep.setter
    def auto_sleep(self, value: bool) -> None:
        if not value and self.machine == Machine.CPU:
            warnings.warn("Disabling auto-sleep will convert the Studio from free to paid!")
        self._studio_api.update_autoshutdown(self._studio.id, self._teamspace.id, enabled=value)
        self._update_studio_reference()

    @property
    def auto_sleep_time(self) -> int:
        """Returns the time in seconds a Studio has to be idle for auto-sleep to kick in (if enabled)."""
        return self._studio.code_config.idle_shutdown_seconds

    @auto_sleep_time.setter
    def auto_sleep_time(self, value: int) -> None:
        warnings.warn("Setting auto-sleep time will convert the Studio from free to paid!")
        self._studio_api.update_autoshutdown(self._studio.id, self._teamspace.id, idle_shutdown_seconds=value)
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
    def env(self) -> Dict[str, str]:
        self._update_studio_reference()
        return self._studio_api.get_env(self._studio)

    def set_env(self, new_env: Dict[str, str], partial: bool = True) -> None:
        """Set the environment variables for the Studio.

        Args:
            new_env: The new environment variables to set.
            partial: Whether to only set the environment variables that are provided.
                If False, existing environment variables that are not in new_env will be removed.
                If True, existing environment variables that are not in new_env will be kept.
        """
        self._studio_api.set_env(self._studio, self._teamspace.id, new_env, partial=partial)

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
            CustomPortPlugin,
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
            "custom-port": CustomPortPlugin,
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
