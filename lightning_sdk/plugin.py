import datetime
import logging
import os
import warnings
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator, Optional, Protocol, Union, runtime_checkable

from lightning_sdk.job import Job
from lightning_sdk.machine import Machine
from lightning_sdk.studio import Studio
from lightning_sdk.utils.resolve import (
    _LIGHTNING_SERVICE_EXECUTION_ID_KEY,
    _resolve_deprecated_cloud_compute,
    _setup_logger,
)

if TYPE_CHECKING:
    from lightning_sdk.lightning_cloud.openapi import Externalv1LightningappInstance
    from lightning_sdk.mmt import MMT

_logger = _setup_logger(__name__)


class _Plugin(ABC):
    """Abstract Plugin class defining the API.

    Args:
        name: the name of the current plugin
        description: the description of the current plugin
        studio: the Studio, the current plugin is installed on

    """

    def __init__(
        self,
        name: str,
        description: str,
        studio: Studio,
    ) -> None:
        self._name = name
        self._description = description
        self._studio = studio
        self._has_been_executed = False

    def install(self) -> None:
        """Installs the plugin on the Studio given at init-time."""
        self._studio.install_plugin(self._name)

    def uninstall(self) -> None:
        """Uninstalls the plugin from the Studio given at init-time."""
        self._studio.uninstall_plugin(self._name)

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Runs the plugin on the Studio given at init-time."""

    @property
    def name(self) -> str:
        """The name of the current plugin."""
        return self._name

    @property
    def description(self) -> str:
        """The description of the current plugin."""
        return self._description

    @property
    def studio(self) -> str:
        """The Studio, the current plugin is installed on."""
        return self._studio.name

    def __repr__(self) -> str:
        """String representation of the current plugin."""
        return f"Plugin(\n\tname={self.name}\n\tdescription={self.description}\n\tstudio={self.studio})"

    def __str__(self) -> str:
        """String representation of the current plugin."""
        return repr(self)

    def __eq__(self, other: "Plugin") -> bool:
        """Checks for equality with other plugins."""
        return (
            type(self) is type(other)
            and self.name == other.name
            and self.description == other.description
            and self._studio == other._studio
        )


class Plugin(_Plugin):
    """Plugin class to handle arbitrary plugins on the Studio.

    While plugins can be installed and uninstalled via the SDK, most of them are designed to be run from the Studio's UI
    only. Calling run just won't do anything in most cases.

    """

    def run(self) -> str:
        """Executes the command of the plugin on the Studio."""
        warnings.warn(
            "While plugins can be installed and uninstalled via the SDK, most of them are designed to "
            "be run from the Studio's UI only. "
            "Calling run just won't do anything in most cases."
        )
        if self._has_been_executed:
            logging.info("This plugin has already been executed and can be run only once per Studio.")
            return None

        output, port = self._studio._execute_plugin(self._name)

        if port > 0:
            self._has_been_executed = True

        return output


class JobsPlugin(_Plugin):
    """Plugin handling asynchronous jobs."""

    _plugin_run_name = "Job"
    _slug_name = "jobs"

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        machine: Machine = Machine.CPU,
        cloud_compute: Optional[Machine] = None,
        interruptible: bool = False,
    ) -> Job:
        """Launches an asynchronous job.

        Args:
            command: The command to be executed.
            name: The name of the job.
            machine: The machine to run the job on.
            interruptible: Whether to run the job on an interruptible machine.
                These are cheaper but can be preempted at any time.
        """
        if not name:
            name = _run_name("job")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        return Job.run(
            name=name,
            machine=machine,
            command=command,
            studio=self._studio,
            teamspace=self._studio.teamspace,
            cloud_account=self._studio.cloud_account,
            interruptible=interruptible,
        )


class MultiMachineTrainingPlugin(_Plugin):
    """Plugin handling multi-machine-training jobs."""

    _plugin_run_name = "Multi-Machine-Training"
    _slug_name = "mmt"

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        machine: Machine = Machine.CPU,
        cloud_compute: Optional[Machine] = None,
        num_instances: int = 2,
        interruptible: bool = False,
    ) -> "MMT":
        """Launches an asynchronous multi-machine-training.

        Args:
            command: The command to be executed.
            name: The name of the job.
            machine: The machine to run the job on.
            num_instances: The number of instances to run the job on.
            interruptible: Whether to run the job on an interruptible machine.
                These are cheaper but can be preempted at any time.
        """
        from lightning_sdk.mmt import MMT

        if not name:
            name = _run_name("dist-run")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        return MMT.run(
            name=name,
            num_machines=num_instances,
            machine=machine,
            command=command,
            studio=self._studio,
            teamspace=self._studio.teamspace,
            interruptible=interruptible,
        )


class MultiMachineDataPrepPlugin(_Plugin):
    """Plugin handling multi machine data processing jobs."""

    _plugin_run_name = "Multi-Machine-Data-Procesing"
    _slug_name = "data-prep"

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        machine: Machine = Machine.CPU,
        cloud_compute: Optional[Machine] = None,
        num_instances: int = 2,
        interruptible: bool = False,
    ) -> Job:
        """Launches an asynchronous multi-machine-data-processing job.

        Args:
            command: The command to be executed.
            name: The name of the job.
            machine: The machine to run the job on.
            num_instances: The number of instances to run the job on.
            interruptible: Whether to run the job on an interruptible machine.
                These are cheaper but can be preempted at any time.
        """
        if not name:
            name = _run_name("data-prep")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        resp = self._studio._studio_api.create_data_prep_machine_job(
            entrypoint=command,
            name=name,
            num_instances=num_instances,
            machine=machine,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cloud_account=self._studio.cloud_account,
            interruptible=interruptible,
        )

        with forced_v1(Job) as v1_job:
            return v1_job(resp.name, self._studio.teamspace)


class InferenceServerPlugin(_Plugin):
    """Plugin handling the asynchronous inference server."""

    _plugin_run_name = "Inference Server"
    _slug_name = ""

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        machine: Machine = Machine.CPU,
        cloud_compute: Optional[Machine] = None,
        min_replicas: int = 1,
        max_replicas: int = 10,
        scale_out_interval: int = 10,
        scale_in_interval: int = 10,
        max_batch_size: int = 4,
        timeout_batching: float = 0.3,
        endpoint: str = "/predict",
        interruptible: bool = False,
    ) -> "Externalv1LightningappInstance":
        """Launches an asynchronous inference server."""
        if name is None:
            name = _run_name("inference-run")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        resp = self._studio._studio_api.create_inference_job(
            entrypoint=command,
            name=name,
            machine=machine,
            min_replicas=str(min_replicas),
            max_replicas=str(max_replicas),
            max_batch_size=str(max_batch_size),
            timeout_batching=str(timeout_batching),
            scale_in_interval=str(scale_in_interval),
            scale_out_interval=str(scale_out_interval),
            endpoint=endpoint,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cloud_account=self._studio.cloud_account,
            interruptible=interruptible,
        )

        _logger.info(_success_message(resp, self))
        with forced_v1(Job) as v1_job:
            return v1_job(resp.name, self._studio.teamspace)


class SlurmJobsPlugin(_Plugin):
    """Plugin handling asynchronous SLURM jobs."""

    _plugin_run_name = "slurm"
    _slug_name = "slurm"

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        cluster_id: Optional[str] = None,
        work_dir: str = "/home/lightning_manager",
        sync_env: bool = True,
        cache_id: Optional[str] = None,
    ) -> "Externalv1LightningappInstance":
        """Launches an asynchronous SLURM job.

        Args:
            command: The command to be passed to the SLURM Job.
            name: The name of the SLURM Job.
            cluster_id: The name of the SLURM Cluster to submit the job on.
                If the cluster_id isn't provided, the oldest running SLURM cluster will be selected.
            work_dir: The position where the the files will be created on the SLURM cluster.
            sync_env: Whether to force an environement sync.
            cache_id: A string to avoid re-downloading the Studio files to the SLURM cluster.
                If you update your files and don't change the cache_id, they won't be used.

        """
        from lightning_sdk.lightning_cloud.openapi import SlurmJobsBody

        if work_dir == "":
            raise ValueError("The argument `work_dir` needs to be a proper path on the SLURM Cluster.")

        if name is None:
            name = _run_name("slurm")

        client = self._studio._studio_api._client

        clusters = client.cluster_service_list_project_clusters(project_id=self._studio._teamspace.id).clusters
        slurm_clusters = [cluster for cluster in clusters if cluster.spec.slurm_v1 is not None]
        running_slurm_clusters = [
            cluster for cluster in slurm_clusters if cluster.status.phase == "CLUSTER_STATE_RUNNING"
        ]
        running_slurm_clusters = sorted(running_slurm_clusters, key=lambda x: x.created_at)

        if not running_slurm_clusters:
            raise RuntimeError(
                "You don't have any running SLURM clusters associated to this project. "
                "Please, check your Teamspace Cloud Account."
            )

        selected_cluster = None

        if cluster_id:
            for cluster in running_slurm_clusters:
                if cluster.cluster_id == cluster_id:
                    selected_cluster = cluster
                    break

            if not selected_cluster:
                raise ValueError(f"The provided cluster {cluster_id} wasn't found.")
        else:
            selected_cluster = running_slurm_clusters[0]

        service_id = os.getenv(_LIGHTNING_SERVICE_EXECUTION_ID_KEY)

        # TODO: Move this to the BE
        envs = [
            f"LIGHTNING_CLOUD_PROJECT_ID={os.getenv('LIGHTNING_CLOUD_PROJECT_ID')}",
            f"LIGHTNING_USERNAME={os.getenv('LIGHTNING_USERNAME')}",
            f"LIGHTNING_USER_ID={os.getenv('LIGHTNING_USER_ID')}",
            f"LIGHTNING_API_KEY={os.getenv('LIGHTNING_API_KEY')}",
            f"LIGHTNING_CLOUD_URL={os.getenv('LIGHTNING_CLOUD_URL')}",
        ]

        if service_id:
            envs.append(f"{_LIGHTNING_SERVICE_EXECUTION_ID_KEY}={service_id}")

        if "&&" in command:
            # We are adding the env varaibles to the latest command
            splits = command.split("&&")
            splits[-1] = " ".join(envs) + " " + splits[-1]
            command = " && ".join(splits)
        else:
            command = " ".join(envs) + " " + command

        resp = client.slurm_jobs_user_service_create_user_slurm_job(
            project_id=self._studio._teamspace.id,
            body=SlurmJobsBody(
                cloudspace_id=self._studio._studio.id,
                cluster_id=selected_cluster.id,
                command=command,
                name=name,
                sync_env=sync_env,
                work_dir=work_dir,
                service_id=service_id,
                cache_id=cache_id,
            ),
        )

        _logger.info(_success_message(resp, self))
        return resp


class CustomPortPlugin(_Plugin):
    """Plugin handling the port of a given service."""

    _plugin_run_name = "Custom Port"
    _slug_name = "custom-port"

    def run(self, name: Optional[str] = None, port: int = 8000) -> str:
        """Starts a new port to the given Studio."""
        if name is None:
            name = _run_name("port")

        return self._studio._studio_api.start_new_port(
            teamspace_id=self._studio._teamspace.id,
            studio_id=self._studio._studio.id,
            name=name,
            port=port,
        )


@runtime_checkable
class _RunnablePlugin(Protocol):
    _plugin_run_name: str
    _slug_name: str

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        machine: Machine = Machine.CPU,
        cloud_compute: Optional[Machine] = None,
        **kwargs: Any,
    ) -> Union["Externalv1LightningappInstance", Job]:
        ...


def _run_name(plugin_type: str) -> str:
    """Creates the run name for a given plugin type."""
    return f"{plugin_type}-{datetime.datetime.now().strftime('%b-%d-%H_%M')}"


def _success_message(resp: Union["Externalv1LightningappInstance", Job], plugin_instance: _RunnablePlugin) -> str:
    """Compiles the success message for a given runnable plugin."""
    return f"{plugin_instance._plugin_run_name} {resp.name} was successfully launched. View it at https://lightning.ai/{plugin_instance._studio.owner.name}/{plugin_instance._studio.teamspace.name}/studios/{plugin_instance.studio}/app?app_id={plugin_instance._slug_name}&job_name={resp.name}"


@contextmanager
def forced_v1(cls: Any) -> Generator[Any, None, None]:
    """Forces to use the v1 version of a class when using a class with multiple backends."""
    orig_val = getattr(cls, "_force_v1", False)
    try:
        cls._force_v1 = True
        yield cls
    finally:
        cls._force_v1 = orig_val
