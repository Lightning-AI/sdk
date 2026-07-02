import os
from typing import List, Optional, Union

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.pipeline_api import PipelineApi
from lightning_sdk.api.utils import AccessibleResource, raise_access_error_if_not_allowed
from lightning_sdk.machine import CloudProvider
from lightning_sdk.organization import Organization
from lightning_sdk.pipeline.printer import PipelinePrinter
from lightning_sdk.pipeline.schedule import _TIMEZONES, Schedule
from lightning_sdk.pipeline.steps import DeploymentStep, JobStep, MMTStep, _get_studio
from lightning_sdk.pipeline.utils import prepare_steps
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import _get_cluster, _resolve_teamspace


class Pipeline:
    def __init__(
        self,
        name: str,
        cloud: Optional[Union[CloudProvider, str]] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        shared_filesystem: Optional[bool] = None,
        studio: Optional[Union[Studio, str]] = None,
        stop_on_failure: bool = True,
        interruption_retries: int = 0,
    ) -> None:
        """The Lightning Pipeline can be used to create complex DAG.

        Arguments:
            name: The desired name of the pipeline.
            cloud: Cloud provider or cloud account to use for the entire pipeline.
            teamspace: The teamspace where the pipeline will be created.
            org: The organization where the pipeline will be created.
            user: The creator of the pipeline.
            shared_filesystem: Whether the pipeline should use a shared filesystem across all nodes.
                Note: This forces the pipeline steps to be in the cloud_account and same region
            stop_on_failure: Whether the pipeline execution should stop if any step fails. Defaults to True.
            interruption_retries: Number of times to retry a step if it is interrupted
                before marking the pipeline as failed. Defaults to 0.

        """
        self._name = name
        self._stop_on_failure = stop_on_failure
        self._interruption_retries = interruption_retries

        self._teamspace = _resolve_teamspace(
            teamspace=teamspace,
            org=org,
            user=user,
        )
        if self._teamspace is None:
            raise RuntimeError("Could not resolve teamspace")

        raise_access_error_if_not_allowed(AccessibleResource.Pipelines, self._teamspace.id)

        self._pipeline_api = PipelineApi()
        self._cloud_account_api = CloudAccountApi()
        self._cloud_account = self._cloud_account_api.resolve_cloud_account(
            self._teamspace.id,
            default_cloud_account=self._teamspace.default_cloud_account,
            cloud=cloud,
        )
        self._default_cluster = _get_cluster(
            client=self._pipeline_api._client, project_id=self._teamspace.id, cluster_id=self._cloud_account
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
        """Submit the pipeline DAG for execution.

        Args:
            steps: Ordered list of pipeline steps to execute.  Must not be empty.
            schedules: Optional cron schedules that trigger the pipeline automatically.

        Raises:
            ValueError: If ``steps`` is empty or a schedule timezone is unsupported.
            RuntimeError: If the teamspace cannot be resolved.
        """
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
                pipeline_step.cloud = self._studio.cloud_account
                pipeline_step.studio = self._studio

            if not pipeline_step.cloud and isinstance(provided_cloud_account, str):
                pipeline_step.cloud = provided_cloud_account

        cloud_account = provided_cloud_account if isinstance(provided_cloud_account, str) else ""

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
            self._stop_on_failure,
            self._interruption_retries,
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
        """Stop a running pipeline execution."""
        if self._pipeline is None:
            return

        self._pipeline_api.stop(self._pipeline)

    def delete(self) -> None:
        """Permanently delete this pipeline and all its runs."""
        if self._pipeline is None:
            return

        self._pipeline_api.delete(self._teamspace.id, self._pipeline.id)

    @property
    def name(self) -> Optional[str]:
        """The pipeline's display name, or ``None`` if it has not been created yet."""
        if self._pipeline:
            return self._pipeline.name
        return None

    @classmethod
    def from_env(cls) -> "Pipeline":
        """Construct a Pipeline from the ``LIGHTNING_PIPELINE_ID`` environment variable.

        Returns:
            Pipeline: A Pipeline instance bound to the running pipeline ID.
        """
        return Pipeline(name=os.getenv("LIGHTNING_PIPELINE_ID", ""))
