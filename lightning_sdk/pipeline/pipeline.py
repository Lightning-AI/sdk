import os
from typing import List, Optional, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.pipeline_api import PipelineApi
from lightning_sdk.machine import CloudProvider
from lightning_sdk.organization import Organization
from lightning_sdk.pipeline.printer import PipelinePrinter
from lightning_sdk.pipeline.schedule import _TIMEZONES, Schedule
from lightning_sdk.pipeline.steps import DeploymentStep, JobStep, MMTStep, _get_studio
from lightning_sdk.pipeline.utils import prepare_steps
from lightning_sdk.services.utilities import _get_cluster
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _resolve_teamspace


class Pipeline:
    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        cloud_account: Optional[str] = None,
        cloud_provider: Optional[Union[CloudProvider, str]] = None,
        shared_filesystem: Optional[bool] = None,
        studio: Optional[Union[Studio, str]] = None,
    ) -> None:
        """The Lightning Pipeline can be used to create complex DAG.

        Arguments:
            name: The desired name of the pipeline.
            teamspace: The teamspace where the pipeline will be created.
            org: The organization where the pipeline will be created.
            user: The creator of the pipeline.
            cloud_account: The cloud account to use for the entire pipeline.
            shared_filesystem: Whether the pipeline should use a shared filesystem across all nodes.
                Note: This forces the pipeline steps to be in the cloud_account and same region
        """
        self._name = name

        self._teamspace = _resolve_teamspace(
            teamspace=teamspace,
            org=org,
            user=user,
        )
        if self._teamspace is None:
            raise RuntimeError("Could not resolve teamspace")

        self._pipeline_api = PipelineApi()
        self._cloud_account_api = CloudAccountApi()
        self._cloud_account = self._cloud_account_api.resolve_cloud_account(
            self._teamspace.id, cloud_account, cloud_provider, self._teamspace.default_cloud_account
        )
        self._default_cluster = _get_cluster(
            client=self._pipeline_api._client, project_id=self._teamspace.id, cluster_id=cloud_account
        )
        self._shared_filesystem = shared_filesystem if shared_filesystem is not None else True
        self._studio = _get_studio(studio)
        self._is_created = False

        pipeline = None

        pipeline = self._pipeline_api.get_pipeline_by_id(self._teamspace.id, name)

        if pipeline:
            self._name = pipeline.name
            self._is_created = True
            self._pipeline = pipeline
        else:
            self._pipeline = None

    def run(
        self, steps: List[Union[JobStep, DeploymentStep, MMTStep]], schedules: Optional[List["Schedule"]] = None
    ) -> None:
        if len(steps) == 0:
            raise ValueError("The provided steps is empty")

        provided_cloud_account = None
        if self._cloud_account:
            provided_cloud_account = self._cloud_account
        elif self._default_cluster:
            provided_cloud_account = self._default_cluster.cluster_id

        for step_idx, pipeline_step in enumerate(steps):
            if pipeline_step.name in [None, ""]:
                pipeline_step.name = f"step-{step_idx}"

            if (
                self._studio is not None
                and (pipeline_step.image == "" or pipeline_step.image is None)
                and pipeline_step.studio is None
            ):
                pipeline_step.cloud_account = self._studio.cloud_account
                pipeline_step.studio = self._studio

            if not pipeline_step.cloud_account and isinstance(provided_cloud_account, str):
                pipeline_step.cloud_account = provided_cloud_account

        cluster_ids = set(step.cloud_account for step in steps if step.cloud_account not in ["", None])  # noqa: C401

        cloud_account = (
            list(cluster_ids)[0] if len(cluster_ids) == 1 and self._cloud_account is None else ""  # noqa: RUF015
        )

        steps = [step.to_proto(self._teamspace, cloud_account, self._shared_filesystem) for step in steps]

        proto_steps = prepare_steps(steps)
        schedules = schedules or []

        for schedule_idx, schedule in enumerate(schedules):
            if schedule.name is None:
                schedule.name = f"schedule-{schedule_idx}"

            if schedule.timezone is not None and schedule.timezone not in _TIMEZONES:
                raise ValueError(
                    f"The schedule {schedule.name} timezone isn't supported. Available list is {_TIMEZONES}. Found {schedule.timezone}."  # noqa: E501
                )

        parent_pipeline_id = None if self._pipeline is None else self._pipeline.id

        self._pipeline = self._pipeline_api.create_pipeline(
            self._name,
            self._teamspace,
            proto_steps,
            self._shared_filesystem,
            schedules,
            parent_pipeline_id,
        )

        printer = PipelinePrinter(
            self._name,
            parent_pipeline_id is None,
            self._pipeline,
            self._teamspace,
            proto_steps,
            schedules,
        )
        printer.print_summary()

    def stop(self) -> None:
        if self._pipeline is None:
            return

        self._pipeline_api.stop(self._pipeline)

    def delete(self) -> None:
        if self._pipeline is None:
            return

        self._pipeline_api.delete(self._teamspace.id, self._pipeline.id)

    @property
    def name(self) -> Optional[str]:
        if self._pipeline:
            return self._pipeline.name
        return None

    @classmethod
    def from_env(cls) -> "Pipeline":
        return Pipeline(name=os.getenv("LIGHTNING_PIPELINE_ID", ""))
