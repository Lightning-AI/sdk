import os
from typing import Optional, Tuple, Mapping, Dict
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    MetricsstreamCreateBody,
    V1Membership,
    MetricsstreamIdBody,
    V1Metrics,
    V1MetricValue,
)
from lightning_sdk.lightning_cloud.env import LIGHTNING_CLOUD_PROJECT_ID
from threading import Thread, Event
from multiprocessing import Queue
from time import time, sleep
import queue
from copy import deepcopy
from datetime import datetime
from google.protobuf import timestamp_pb2
from google.protobuf.json_format import MessageToDict

_PUSH_TO_QUEUE_SLEEP = 1
_MAX_LOG_METRICS_IN_SECOND = 10

class _SenderThread(Thread):

    def __init__(
        self,
        project_id: str,
        id: str,
        client: LightningClient,
        metrics_queue: Queue,
        is_ready_event: Event,
        stop_event: Event,
        done_event: Event,
        rate_limiting: int = 1
    ):
        super().__init__(daemon=True)
        self.project_id = project_id
        self.id = id
        self.client = client
        self.metrics_queue = metrics_queue
        self.last_time = time()
        self.rate_limiting = rate_limiting
        self.is_ready_event = is_ready_event
        self.stop_event = stop_event
        self.done_event = done_event
        self.metrics: Dict[str, V1Metrics] = {}
        self.exception = None

    def run(self):
        try:
            self.is_ready_event.set()

            while not self.stop_event.is_set():
                try:
                    metrics = self.metrics_queue.get(timeout=1)
                    for name, values in metrics.items():
                        if name not in self.metrics:
                            self.metrics[name] = V1Metrics(name=name, values=values.values)
                        else:
                            self.metrics[name].values.extend(values.values)
                except queue.Empty:
                    pass

                if (time() - self.last_time) < self.rate_limiting:
                    continue

                metrics = list(self.metrics.values())
                num_values = sum([len(m.values) for m in metrics])

                if num_values == 0:
                    continue

                self.client.lit_logger_service_append_metrics(
                    project_id=self.project_id,
                    id=self.id,
                    body= MetricsstreamIdBody(
                        metrics=metrics,
                    ),
                )

                self.last_time = time()

                self.metrics = {}

            while True:
                try:
                    metrics = self.metrics_queue.get(timeout=1)
                    for name, values in metrics.items():
                        if name not in self.metrics:
                            self.metrics[name] = V1Metrics(name=name, values=values.values)
                        else:
                            self.metrics[name].values.extend(values.values)
                except queue.Empty:
                    break

            if self.metrics:
                self.client.lit_logger_service_append_metrics(
                    project_id=self.project_id,
                    id=self.id,
                    body=MetricsstreamIdBody(metrics=list(self.metrics.values()))
                )

            self.done_event.set()
        except Exception as e:
            print(e)
            self.exception = e


class Logger:

    def __init__(
        self,
        name: str,
        project_id: Optional[str] = None,
    ):
        """The base class to enable logging to the https://lightning.ai Platform
        
        Arguments:
            name: The name of your experiement
            project_id: The project on which you want to attach your charts.

        Example::

            from lightning_sdk.lightning_cloud.logger import Experiment
            from time import sleep
            import random

            stream = Experiment("my-name")

            for i in range(1_000_000):
                stream.log_metrics({"i": random.random()})
                sleep(1 / 100000)

            stream.finalize()
        """

        self.name = name
        self.project_id = project_id
        self.done_event = Event()

        auth = Auth()
        auth.authenticate()
    
        self.client = LightningClient(retry=False)
        self.project = _get_project(self.client, project_id=self.project_id)

        self.stream = self.client.lit_logger_service_create_metrics_stream(
            project_id=self.project.project_id,
            body=MetricsstreamCreateBody(
                name=self.name,
                cloudspace_id=os.getenv("LIGHTNING_CLOUD_SPACE_ID"),
                app_id=os.getenv("LIGHTNING_CLOUD_APP_ID"),
                work_id=os.getenv("LIGHTNING_CLOUD_WORK_ID"),
            ))

        self.metrics_queue = Queue()
        self.stop_event = Event()
        self.is_ready_event = Event()
        self.sender = _SenderThread(
            self.stream.project_id,
            self.stream.id,
            self.client,
            self.metrics_queue,
            self.is_ready_event,
            self.stop_event,
            self.done_event,
        )
        self.sender.start()
        self.metrics: Dict[str, V1Metrics] = {}
        self.last_time = None

        # wait for the thead to be started
        while not self.is_ready_event.is_set():
            sleep(0.1)

        sleep(1)

    def log_metrics(self, metrics: Mapping[str, float], step: Optional[int] = None) -> None:
        if self.last_time is None:
            self.last_time = time()

        if self.sender.exception is None:
            for name, value in metrics.items():
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(datetime.now())
                value = V1MetricValue(value=float(value), created_at=MessageToDict(timestamp))
                if name not in self.metrics:
                    self.metrics[name] = V1Metrics(name=name, values=[value])
                else:
                    self.metrics[name].values.append(value)

            should_send = time() - self.last_time > _PUSH_TO_QUEUE_SLEEP

            if time() - self.last_time > _PUSH_TO_QUEUE_SLEEP:
                self._send()
        else:
            raise self.sender.exception

    def finalize(self):
        self._send()
        self.stop_event.set()

        sleep(5)

        # wait for all the metrics to be uploaded
        while not self.done_event.is_set() or not self.metrics_queue.empty():
            sleep(1)

    def _send(self):
        if not len(self.metrics):
            return

        metrics = deepcopy(self.metrics)
        num_values = sum([len(m.values) for m in metrics.values()])
        if num_values > (_MAX_LOG_METRICS_IN_SECOND * _PUSH_TO_QUEUE_SLEEP):
            raise RuntimeError(
                f"You are generating too much metrics. The limit is {int(_MAX_LOG_METRICS_IN_SECOND)} values per second."
                f" You logged {len(metrics) / _PUSH_TO_QUEUE_SLEEP} values."
            )

        self.metrics_queue.put(metrics)
        self.metrics = {}
        self.last_time = time()


def _get_project(client: LightningClient, project_id: Optional[str] = None, verbose: bool = True) -> V1Membership:
    """Get a project membership for the user from the backend."""
    if project_id is None:
        project_id = LIGHTNING_CLOUD_PROJECT_ID

    if project_id is not None:
        project = client.projects_service_get_project(project_id)
        if not project:
            raise ValueError(
                "Environment variable `LIGHTNING_CLOUD_PROJECT_ID` is set but could not find an associated project."
            )
        return V1Membership(
            name=project.name,
            display_name=project.display_name,
            description=project.description,
            created_at=project.created_at,
            project_id=project.id,
            owner_id=project.owner_id,
            owner_type=project.owner_type,
            quotas=project.quotas,
            updated_at=project.updated_at,
        )

    projects = client.projects_service_list_memberships()
    if len(projects.memberships) == 0:
        raise ValueError("No valid projects found. Please reach out to lightning.ai team to create a project")
    if len(projects.memberships) > 1 and verbose:
        print(f"Defaulting to the project: {projects.memberships[0].name}")
    return projects.memberships[0]