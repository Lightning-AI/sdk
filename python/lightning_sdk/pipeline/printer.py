import os
from typing import Any, ClassVar, Dict, List

from lightning_sdk.lightning_cloud.openapi.models import V1Pipeline, V1PipelineStepType, V1Schedule
from lightning_sdk.pipeline.utils import _get_spec


class PipelinePrinter:
    """A helper class to print a formatted summary of a pipeline."""

    STEP_TYPE_MAP: ClassVar[Dict[str, str]] = {
        V1PipelineStepType.DEPLOYMENT: "Deployment",
        V1PipelineStepType.JOB: "Job",
        V1PipelineStepType.MMT: "MMT",
    }

    def __init__(
        self,
        name: str,
        initial: bool,
        pipeline: V1Pipeline,
        teamspace: Any,
        proto_steps: List[Any],
        schedules: List[V1Schedule],
    ) -> None:
        self._name = name
        self._initial = initial
        self._pipeline = pipeline
        self._teamspace = teamspace
        self._proto_steps = proto_steps
        self._shared_filesystem = pipeline.shared_filesystem
        self._schedules = schedules
        cluster_ids: set[str] = set()
        for step in self._proto_steps:
            job_spec = _get_spec(step)
            cluster_ids.add(job_spec.cluster_id)
        self._cluster_ids = cluster_ids

    def print_summary(self) -> None:
        """Prints the full, formatted summary of the created pipeline."""
        self._print("\n" + "─" * 60)
        self._print(f"✅ Pipeline '{self._name}' {'created' if self._initial else 'updated'} successfully!")
        self._print("─" * 60)

        self._print_steps()
        self._print_schedules()
        self._print_cloud_account()
        self._print_shared_filesystem()
        self._print_footer()

    def _print(self, value: str) -> None:
        print(value)

    def _print_steps(self) -> None:
        """Prints the formatted list of pipeline steps."""
        self._print("\nWorkflow Steps:")
        if not self._proto_steps:
            self._print("  - No steps defined.")
            return

        for i, step in enumerate(self._proto_steps):
            step_type = self.STEP_TYPE_MAP.get(step.type, "Unknown Step")

            # Format the 'wait_for' list for cleaner output
            if not step.wait_for:
                wait_for_str = "(runs first)"
            else:
                # e.g., "'step_a', 'step_b'"
                wait_for_str = f" waits for {', '.join([f'{w}' for w in step.wait_for])}"

            self._print(f"  ➡️ {i+1}. {step_type} '{step.name}' - {wait_for_str}")

    def _print_schedules(self) -> None:
        """Prints the formatted list of schedules."""
        self._print("\n🗓️ Schedules:")
        if not self._schedules:
            self._print("  - No schedules defined.")
            return

        for schedule in self._schedules:
            self._print(
                f"  - '{schedule.name}' runs on cron schedule: `{schedule.cron_expression} in timezone {schedule.timezone or 'UTC'}` with parallel_runs={schedule.parallel_runs or False}"  # noqa: E501
            )

    def _print_footer(self) -> None:
        """Prints the final link and closing message."""
        cloud_url = os.getenv("LIGHTNING_CLOUD_URL", "https://lightning.ai").replace(":443", "")

        # Using properties of assumed objects for a cleaner look
        owner: str = self._teamspace.owner.name
        team: str = self._teamspace.name
        pipeline_name: str = self._name

        pipeline_url = f"{cloud_url}/{owner}/{team}/pipelines/{pipeline_name}?app_id=pipeline"

        self._print("\n" + "─" * 60)
        self._print(f"🔗 View your pipeline in the browser:\n   {pipeline_url}")
        self._print("─" * 60 + "\n")

    def _print_cloud_account(self) -> None:
        if not self._proto_steps:
            return

        self._print(f"\nCloud account{'s' if len(self._cluster_ids) > 1 else ''}:")
        for cluster_id in sorted(self._cluster_ids):
            self._print(f"  - {cluster_id}")

    def _print_shared_filesystem(self) -> None:
        self._print(f"\nShared filesystem: {self._shared_filesystem.enabled}")

        if self._shared_filesystem.enabled and len(self._cluster_ids) == 1:
            shared_path = ""
            cluster_id = list(self._cluster_ids)[0]  # noqa: RUF015
            if self._pipeline.shared_filesystem.s3_folder:
                shared_path = f"/teamspace/s3_folders/pipelines-{cluster_id}"
            if self._pipeline.shared_filesystem.gcs_folder:
                shared_path = f"/teamspace/gcs_folders/pipelines-{cluster_id}"
            if self._pipeline.shared_filesystem.efs:
                shared_path = f"/teamspace/efs_connections/pipelines-{cluster_id}"
            if self._pipeline.shared_filesystem.filestore:
                shared_path = f"/teamspace/gcs_connections/pipelines-{cluster_id}"

            if shared_path:
                self._print(f"  - {shared_path}")
