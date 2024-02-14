import datetime
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

from lightning_sdk.machine import Machine
from lightning_sdk.studio import Studio
from lightning_sdk.utils import _resolve_deprecated_cloud_compute, _setup_logger

if TYPE_CHECKING:
    from lightning_sdk.lightning_cloud.openapi import Externalv1LightningappInstance

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
    """Plugin class to handle arbitrary plugins on the Studio."""

    def run(self) -> str:
        """Executes the command of the plugin on the Studio."""
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
    ) -> "Externalv1LightningappInstance":
        """Launches an asynchronous job."""
        if name is None:
            name = _run_name("job")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        resp = self._studio._studio_api.create_job(
            entrypoint=command,
            name=name,
            machine=machine,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )

        _logger.info(_success_message(resp, self))
        return resp


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
        strategy: str = "parallel",
    ) -> "Externalv1LightningappInstance":
        """Launches an asynchronous multi-machine-training."""
        if name is None:
            name = _run_name("dist-run")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        # TODO: assert num_instances >=2
        resp = self._studio._studio_api.create_multi_machine_job(
            entrypoint=command,
            name=name,
            num_instances=num_instances,
            machine=machine,
            strategy=strategy,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )

        _logger.info(_success_message(resp, self))
        return resp


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
    ) -> "Externalv1LightningappInstance":
        """Launches an asynchronous multi-machine-processing-job."""
        if name is None:
            name = _run_name("data-prep")

        machine = _resolve_deprecated_cloud_compute(machine, cloud_compute)

        resp = self._studio._studio_api.create_data_prep_machine_job(
            entrypoint=command,
            name=name,
            num_instances=num_instances,
            machine=machine,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )

        _logger.info(_success_message(resp, self))
        return resp


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
            cluster_id=self._studio._studio.cluster_id,
        )

        _logger.info(_success_message(resp, self))
        return resp


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
    ) -> "Externalv1LightningappInstance":
        ...


def _run_name(plugin_type: str) -> str:
    """Creates the run name for a given plugin type."""
    return f"{plugin_type}-{datetime.datetime.now().strftime('%b-%d-%H_%M')}"


def _success_message(resp: "Externalv1LightningappInstance", plugin_instance: _RunnablePlugin) -> str:
    """Compiles the success message for a given runnable plugin."""
    return f"{plugin_instance._plugin_run_name} {resp.name} was successfully launched. View it at https://lightning.ai/{plugin_instance._studio.owner.name}/{plugin_instance._studio.teamspace.name}/studios/{plugin_instance.studio}/app?app_id={plugin_instance._slug_name}&job_name={resp.name}"
