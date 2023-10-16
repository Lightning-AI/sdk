from typing import Any, List, Optional, Protocol, runtime_checkable, TYPE_CHECKING
import logging
from abc import ABC, abstractmethod
from lightning_sdk.studio import Studio
import datetime
from  lightning_sdk.machine import Machine
from lightning_sdk.utils import _setup_logger

if TYPE_CHECKING:
    from lightning_sdk.lightning_cloud.openapi import Externalv1LightningappInstance

_logger = _setup_logger(__name__)


class _Plugin(ABC):
    def __init__(
        self,
        name: str,
        description: str,
        studio: Studio,
    ):
        self._name = name
        self._description = description
        self._studio = studio
        self._has_been_executed = False

    def install(self):
        self._studio._install_plugin(self._name)

    def uninstall(self):
        self._studio._uninstall_plugin(self._name)

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        pass

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def studio(self) -> str:
        return self._studio.name

    def __repr__(self):
        return f"Plugin(\n\tname={self.name}\n\tdescription={self.description}\n\tstudio={self.studio})"
    
    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name and self.description == other.description and self._studio == other._studio


class Plugin(_Plugin):
    def run(self):
        if self._has_been_executed:
            logging.info("This plugin has already been executed and can be run only once per Studio.")
            return

        output, port = self._studio._execute_plugin(self._name)

        if port > 0:
            self._has_been_executed = True

        return output


class JobsPlugin(_Plugin):
    _plugin_run_name = "Job"
    _slug_name = "jobs"
    
    def run(
        self,
        command: str,
        name: Optional[str] = None,
        cloud_compute: Machine = Machine.CPU,
    ):
        if name is None:
            name = _run_name("job")
        resp =  self._studio._studio_api.create_job(
            entrypoint=command,
            name=name,
            cloud_compute=cloud_compute,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )

        _logger.info(_success_message(resp, self))
        return resp


class MultiMachineTrainingPlugin(_Plugin):
    _plugin_run_name = "Multi-Machine-Training"
    _slug_name = "mmt"

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        cloud_compute: Machine = Machine.CPU,
        num_instances: int = 2,
        strategy: str = "parallel",
    ):
        if name is None:
            name = _run_name("dist-run")

        # TODO: assert num_instances >=2
        resp =  self._studio._studio_api.create_multi_machine_job(
            entrypoint=command,
            name=name,
            num_instances=num_instances,
            cloud_compute=cloud_compute,
            strategy=strategy,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )

        _logger.info(_success_message(resp, self))
        return resp


class InferenceServerPlugin(_Plugin):
    _plugin_run_name = "Inference Server"
    _slug_name = ""
    def run(
        self,
        command: str,
        name: Optional[str] = None,
        cloud_compute: Machine = Machine.CPU,
        min_replicas: int = 1,
        max_replicas: int = 10,
        scale_out_interval: int = 10,
        scale_in_interval: int = 10,
        max_batch_size: int = 4,
        timeout_batching: float = 0.3,
        endpoint: str = "/predict",
    ):
        if name is None:
            name = _run_name("inference-run")

        resp = self._studio._studio_api.create_inference_job(
            entrypoint=command,
            name=name,
            cloud_compute=cloud_compute,
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

    def run(self, command: str, name: Optional[str]=None, cloud_compute: Machine = Machine.CPU, **kwargs):
        ...

def _run_name(plugin_type: str):
    return f"{plugin_type}-{datetime.datetime.now().strftime('%b-%d-%H_%M')}"

def _success_message(resp: "Externalv1LightningappInstance", plugin_instance: _RunnablePlugin):
    return f"{plugin_instance._plugin_run_name} {resp.name} was successfully launched. View it at https://lightning.ai/{plugin_instance._studio.owner}/{plugin_instance._studio._teamspace.name}/studios/{plugin_instance.studio}/app?app_id={plugin_instance._slug_name}&job_name={resp.name}"
