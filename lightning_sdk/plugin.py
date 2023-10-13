from typing import Any, List, Optional
import logging
from abc import ABC, abstractmethod
from lightning_sdk.studio import Studio
import datetime


class _Plugin(ABC):
    def __init__(
        self,
        name: str,
        studio: Studio,
    ):
        self._name = name
        self._studio = studio
        self._has_been_executed = False

    def install(self):
        self._studio._install_plugin(self._name)

    def uninstall(self):
        self._studio._uninstall_plugin(self._name)

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        pass

    def __repr__(self):
        return f"Plugin(\n\tname={self._name}\n\tstudio={self._studio.name})"


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
    def run(
        self,
        entrypoint: str,
        name: Optional[str] = None,
        cloud_compute: Machine = Machine.CPU,
    ):
        if name is None:
            name = _run_name("job")
        return self._studio._studio_api.create_job(
            entrypoint=entrypoint,
            name=name,
            cloud_compute=cloud_compute,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )


class MultiMachineTrainingPlugin(_Plugin):
    def run(
        self,
        entrypoint: str,
        name: Optional[str] = None,
        cloud_compute: Machine = Machine.CPU,
        num_instances: int = 2,
        strategy: str = "parallel",
    ):
        if name is None:
            name = _run_name("dist-run")

        # TODO: assert num_instances >=2
        return self._studio._studio_api.create_multi_machine_job(
            entrypoint=entrypoint,
            name=name,
            num_instances=num_instances,
            cloud_compute=cloud_compute,
            strategy=strategy,
            studio_id=self._studio._studio.id,
            teamspace_id=self._studio._teamspace.id,
            cluster_id=self._studio._studio.cluster_id,
        )


class InferenceServer(_Plugin):
    def run(
        self,
        entrypoint: str,
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

        return self._studio._studio_api.create_inference_job(
            entrypoint=entrypoint,
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


def _run_name(plugin_type: str):
    return f"{plugin_type}-{datetime.datetime.now().strftime('%b-%d-%H_%M')}"


class Plugin:
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """"""
        ...

    @property
    def id(self) -> str:
        """"""
        ...

    def studio(self) -> Studio:
        """"""
        ...


class JobPlugin(Plugin):
    # TODO: make machine an actual machine type
    def run(self, *commands: str, machine: Optional[str] = None) -> Job:
        """"""
        ...


class Job:
    """"""

    def __init__(
        self,
        name: str,
    ) -> None:
        self._name = name

    @property
    def status(self) -> Status:
        """"""
        ...

    @property
    def works(self) -> List[Work]:
        """"""
        ...

    @property
    def stop(self):
        """"""
        # stop all works and orchestrator
        ...
