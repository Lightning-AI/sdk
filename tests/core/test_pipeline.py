import inspect
from unittest.mock import MagicMock

import pytest

from lightning_sdk import studio as studio_module
from lightning_sdk import teamspace
from lightning_sdk.api import pipeline_api
from lightning_sdk.lightning_cloud.openapi.models import (
    ProjectIdJobsBody,
    V1JobSpec,
    V1PipelineStep,
    V1PipelineStepType,
    V1SharedFilesystem,
)
from lightning_sdk.machine import Machine
from lightning_sdk.pipeline import DeploymentReleaseStep, DeploymentStep, JobStep, MMTStep, Pipeline
from lightning_sdk.pipeline import pipeline as pipeline_module
from lightning_sdk.pipeline.printer import PipelinePrinter
from lightning_sdk.pipeline.utils import DEFAULT, prepare_steps
from lightning_sdk.utils.resolve import skip_studio_init


def test_pipeline_run(monkeypatch):
    monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
    monkeypatch.setattr(pipeline_module, "_get_cluster", MagicMock())
    pipeline_api_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "PipelineApi", pipeline_api_mock)
    resolve_teamspace_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "_resolve_teamspace", resolve_teamspace_mock)

    pipeline = Pipeline(name="first-pipeline", org="org", user="user", cloud_account="cluster-id")
    cloud_account_mock = MagicMock()
    cloud_account_mock.cluster_id = ""
    pipeline._cloud_account = cloud_account_mock

    assert resolve_teamspace_mock._mock_mock_calls[0].kwargs["org"] == "org"
    assert resolve_teamspace_mock._mock_mock_calls[0].kwargs["user"] == "user"

    with pytest.raises(ValueError, match="You can only reference prior steps"):
        pipeline.run(
            steps=[
                JobStep(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
                JobStep(
                    name="job-1",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    wait_for=["job-1"],
                ),
            ]
        )

    with pytest.raises(ValueError, match="The step 1 doesn't have a valid wait_for. Found job-3"):
        pipeline.run(
            steps=[
                JobStep(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
                JobStep(
                    name="job-1",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    wait_for=["job-3"],
                ),
            ]
        )

    with pytest.raises(ValueError, match="You can only reference prior steps"):
        pipeline.run(
            steps=[
                JobStep(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
                JobStep(
                    name="job-1",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    wait_for=["job-2"],
                ),
                JobStep(
                    name="job-2",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
            ]
        )

    pipeline._pipeline = None

    pipeline.run(
        steps=[
            JobStep(
                name="job-0",
                machine=Machine.CPU,
                command="echo 'Hello, World!'",
                image="ubuntu:latest",
            ),
            JobStep(
                name="job-1", machine=Machine.CPU, command="echo 'Hello, World!'", image="ubuntu:latest", wait_for=None
            ),
            JobStep(
                name="job-2",
                machine="cpu-8",
                command="echo 'Hello, World!'",
                image="ubuntu:latest",
            ),
        ]
    )

    args = pipeline_api_mock().create_pipeline._mock_mock_calls[0].args

    assert "get_pipeline_by_id().name" in str(args[0])
    assert args[-1] is None

    generated = pipeline_api_mock().create_pipeline._mock_mock_calls[0].args[2]

    step_1 = V1PipelineStep(
        name="job-0",
        type=V1PipelineStepType.JOB,
        wait_for=[],
        job=ProjectIdJobsBody(
            name="job-0",
            spec=V1JobSpec(
                command="echo 'Hello, World!'",
                entrypoint="sh -c",
                image="ubuntu:latest",
                instance_name="cpu-4",
                cluster_id="",
                cloudspace_id="",
                env=[],
                image_cluster_credentials=False,
                image_secret_ref="",
                path_mappings=[],
                run_id="",
                spot=False,
            ),
        ),
    )

    step_2 = V1PipelineStep(
        name="job-1",
        type=V1PipelineStepType.JOB,
        wait_for=[],
        job=ProjectIdJobsBody(
            name="job-1",
            spec=V1JobSpec(
                command="echo 'Hello, World!'",
                entrypoint="sh -c",
                image="ubuntu:latest",
                instance_name="cpu-4",
                cluster_id="",
                cloudspace_id="",
                env=[],
                image_cluster_credentials=False,
                image_secret_ref="",
                path_mappings=[],
                run_id="",
                spot=False,
            ),
        ),
    )

    step_3 = V1PipelineStep(
        name="job-2",
        type=V1PipelineStepType.JOB,
        wait_for=["job-0", "job-1"],
        job=ProjectIdJobsBody(
            name="job-2",
            spec=V1JobSpec(
                command="echo 'Hello, World!'",
                entrypoint="sh -c",
                image="ubuntu:latest",
                instance_name="cpu-8",
                cluster_id="",
                cloudspace_id="",
                env=[],
                image_cluster_credentials=False,
                image_secret_ref="",
                path_mappings=[],
                run_id="",
                spot=False,
            ),
        ),
    )

    assert step_1 == generated[0]
    assert step_2 == generated[1]
    assert step_3 == generated[2]


def test_job_parameters_stay_in_sync():
    from lightning_sdk.job import Job
    from lightning_sdk.pipeline.steps import JobStep

    job_signature = inspect.signature(Job.run)
    job_type_signature = inspect.signature(JobStep.__init__)

    job_keys = job_signature.parameters.keys()
    job_type_keys = job_type_signature.parameters.keys()

    # ignore the depreceated parameters
    job_keys = [key for key in job_keys if key not in ["artifacts_local", "artifacts_remote", "cluster"]]
    job_type_keys = [key for key in job_type_keys if key not in ["wait_for", "self"]]

    assert sorted(job_keys) == sorted(job_type_keys)


def test_prepare_steps():
    steps = [
        V1PipelineStep(name="a", wait_for=DEFAULT),
        V1PipelineStep(name="b", wait_for=DEFAULT),
        V1PipelineStep(name="c", wait_for=DEFAULT),
        V1PipelineStep(name="d", wait_for=DEFAULT),
        V1PipelineStep(name="e", wait_for=DEFAULT),
    ]
    steps = prepare_steps(steps)
    assert steps[0].wait_for == []
    assert steps[1].wait_for == ["a"]
    assert steps[2].wait_for == ["b"]
    assert steps[3].wait_for == ["c"]
    assert steps[4].wait_for == ["d"]

    steps = [
        V1PipelineStep(name="a", wait_for=DEFAULT),
        V1PipelineStep(name="b", wait_for=[]),
        V1PipelineStep(name="c", wait_for=DEFAULT),
        V1PipelineStep(name="d", wait_for=DEFAULT),
        V1PipelineStep(name="e", wait_for=DEFAULT),
    ]
    steps = prepare_steps(steps)
    assert steps[0].wait_for == []
    assert steps[1].wait_for == []
    assert steps[2].wait_for == ["a", "b"]
    assert steps[3].wait_for == ["c"]
    assert steps[4].wait_for == ["d"]

    steps = [
        V1PipelineStep(name="a", wait_for=DEFAULT),
        V1PipelineStep(name="b", wait_for=[]),
        V1PipelineStep(name="c", wait_for=DEFAULT),
        V1PipelineStep(name="d", wait_for=[]),
        V1PipelineStep(name="e", wait_for=[]),
    ]
    steps = prepare_steps(steps)
    assert steps[0].wait_for == []
    assert steps[1].wait_for == []
    assert steps[2].wait_for == ["a", "b"]
    assert steps[3].wait_for == []
    assert steps[4].wait_for == []

    steps = [
        V1PipelineStep(name="a", wait_for=DEFAULT),
        V1PipelineStep(name="b", wait_for=[]),
        V1PipelineStep(name="c", wait_for=DEFAULT),
        V1PipelineStep(name="d", wait_for=[]),
        V1PipelineStep(name="e", wait_for=[]),
        V1PipelineStep(name="f", wait_for=DEFAULT),
    ]
    steps = prepare_steps(steps)
    assert steps[0].wait_for == []
    assert steps[1].wait_for == []
    assert steps[2].wait_for == ["a", "b"]
    assert steps[3].wait_for == []
    assert steps[4].wait_for == []
    assert steps[5].wait_for == ["c", "d", "e"]


def test_deployment_default():
    deployment = DeploymentStep(machine=Machine.CPU)
    assert deployment.replicas == 1
    assert deployment.autoscale.min_replicas == 0
    assert deployment.autoscale.max_replicas == 1
    assert deployment.autoscale.target_metrics[0].name == "CPU"
    assert deployment.autoscale.target_metrics[0].target == 80

    deployment = DeploymentStep(machine=Machine.A10G)
    assert deployment.autoscale.target_metrics[0].name == "GPU"


def test_mmt():
    mmt = MMTStep(name="mmt-0", machine=Machine.CPU)
    proto = mmt.to_proto(MagicMock(), "", False)
    assert proto.type == V1PipelineStepType.MMT
    assert proto.name == "mmt-0"
    assert proto.mmt is not None
    assert proto.job is None
    assert proto.deployment is None
    assert proto.mmt.machines == 2
    assert proto.mmt.spec.instance_name == "cpu-4"


def test_stop(monkeypatch):
    monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
    monkeypatch.setattr(pipeline_module, "_get_cluster", MagicMock())
    resolve_teamspace_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "_resolve_teamspace", resolve_teamspace_mock)

    mock_client = MagicMock()
    monkeypatch.setattr(pipeline_api, "LightningClient", mock_client)

    pipeline_spec = MagicMock()
    pipeline_spec.id = "pipeline_id"
    pipeline = Pipeline(name="first-pipeline")
    pipeline._pipeline = MagicMock(return_value=pipeline_spec)
    pipeline._pipeline.name = "something-else"
    pipeline.stop()
    mock_client().pipelines_service_update_pipeline.assert_called()
    assert pipeline.name == "something-else"


def test_delete(monkeypatch):
    monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
    monkeypatch.setattr(pipeline_module, "_get_cluster", MagicMock())
    resolve_teamspace_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "_resolve_teamspace", resolve_teamspace_mock)

    mock_client = MagicMock()
    monkeypatch.setattr(pipeline_api, "LightningClient", mock_client)

    pipeline_spec = MagicMock()
    pipeline_spec.id = "pipeline_id"
    pipeline = Pipeline(name="first-pipeline")
    pipeline._pipeline = MagicMock(return_value=pipeline_spec)
    pipeline.delete()
    mock_client().pipelines_service_delete_pipeline.assert_called()


def test_shared_filesystem(monkeypatch):
    monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
    monkeypatch.setattr(pipeline_module, "_get_cluster", MagicMock())
    pipeline_api_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "PipelineApi", pipeline_api_mock)
    resolve_teamspace_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "_resolve_teamspace", resolve_teamspace_mock)

    pipeline = Pipeline(name="first-pipeline")
    cloud_account_mock = MagicMock()
    cloud_account_mock.cluster_id = "cluster_id_1"
    pipeline._cloud_account = cloud_account_mock

    pipeline.run(
        steps=[
            JobStep(
                name="job-0",
                machine=Machine.CPU,
                command="echo 'Hello, World!'",
                image="ubuntu:latest",
                cloud_account="cluster_id_2",
            ),
        ]
    )

    mock_calls = pipeline_api_mock().create_pipeline._mock_mock_calls
    assert len(mock_calls[0].args)
    assert mock_calls[0].args[-3] is True
    assert isinstance(mock_calls[0].args[-2], list)
    assert len(mock_calls[0].args[-2]) == 0
    assert "get_pipeline_by_id().id" in str(mock_calls[0].args[-1])

    pipeline._shared_filesystem = True


def test_pipeline_with_studio_job_step(monkeypatch):
    with skip_studio_init():
        monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
        monkeypatch.setattr(pipeline_module, "_get_cluster", MagicMock())
        pipeline_api_mock = MagicMock()
        monkeypatch.setattr(pipeline_module, "PipelineApi", pipeline_api_mock)
        resolve_teamspace_mock = MagicMock()
        monkeypatch.setattr(pipeline_module, "_resolve_teamspace", resolve_teamspace_mock)
        monkeypatch.setattr(studio_module, "_resolve_teamspace", resolve_teamspace_mock)
        monkeypatch.setattr(studio_module, "StudioApi", MagicMock())

        pipeline = Pipeline(name="first-pipeline")
        cloud_account_mock = MagicMock()
        cloud_account_mock.cluster_id = "cluster_id_1"
        pipeline._cloud_account = cloud_account_mock

        with pytest.raises(ValueError, match="The provided cloud account"):
            pipeline.run(
                steps=[
                    JobStep(
                        name="job-0",
                        machine=Machine.CPU,
                        command="echo 'Hello, World!'",
                        studio="my-studio",
                        cloud_account="any_cloud_account",
                    ),
                ]
            )

        pipeline.run(
            steps=[
                JobStep(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    studio="my-studio",
                ),
            ]
        )


class TestPrinter(PipelinePrinter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = []

    def _print(self, value):
        self.values.append(value)

    def get_output_as_string(self):
        """Helper to join all captured lines into a single string for easy searching."""
        return "\n".join(self.values)


def test_print_summary_with_multiple_clusters():
    """
    Tests the main scenario: a full pipeline with steps, schedules,
    and multiple unique cloud accounts (clusters).
    """
    # 1. Arrange: Set up all the mock objects
    pipeline = MagicMock()
    pipeline.name = "my-multi-cluster-pipeline"
    pipeline.shared_filesystem = V1SharedFilesystem(enabled=True, s3_folder=True)
    teamspace = MagicMock()
    teamspace.owner.name = "test-user"
    teamspace.name = "test-team"

    # Create mock steps with different types and cluster IDs
    step1 = MagicMock()
    step1.name = "data-prep"
    step1.type = V1PipelineStepType.JOB
    step1.wait_for = []
    step1.job.spec.cluster_id = "cluster-A"

    step2 = MagicMock(type=V1PipelineStepType.DEPLOYMENT, wait_for=["data-prep"])
    step2.name = "training"
    step2.deployment.spec.cluster_id = "cluster-B"

    # Add a third step that re-uses a cluster ID to test the `set` logic
    step3 = MagicMock(type=V1PipelineStepType.JOB, wait_for=["training"])
    step3.name = "eval"
    step3.job.spec.cluster_id = "cluster-A"

    schedule1 = MagicMock(cron_expression="0 0 * * *")
    schedule1.name = "daily-run"

    # 2. Act: Run the method on the test class
    test_printer = TestPrinter(
        "my-multi-cluster-pipeline",
        True,
        pipeline=pipeline,
        teamspace=teamspace,
        proto_steps=[step1, step2, step3],
        schedules=[schedule1],
    )
    test_printer.print_summary()
    output = test_printer.get_output_as_string()

    assert (
        output
        == "\n────────────────────────────────────────────────────────────\n✅ Pipeline 'my-multi-cluster-pipeline' created successfully!\n────────────────────────────────────────────────────────────\n\nWorkflow Steps:\n  ➡️ 1. Job 'data-prep' - (runs first)\n  ➡️ 2. Deployment 'training' -  waits for data-prep\n  ➡️ 3. Job 'eval' -  waits for training\n\n🗓️ Schedules:\n  - 'daily-run' runs on cron schedule: `0 0 * * *`\n\nCloud accounts:\n  - cluster-A\n  - cluster-B\n\nShared filesystem: True\n\n────────────────────────────────────────────────────────────\n🔗 View your pipeline in the browser:\n   https://lightning.ai/test-user/test-team/pipelines/my-multi-cluster-pipeline?app_id=pipeline\n────────────────────────────────────────────────────────────\n"  # noqa: E501
    )


def test_print_summary_with_single_cluster():
    """Tests that the cloud account label is singular when all steps use the same cluster."""
    pipeline = MagicMock(name="my-single-cluster-pipeline")
    teamspace = MagicMock(name="test-team", owner=MagicMock(name="test-user"))

    step1 = MagicMock(name="step-a", type=V1PipelineStepType.JOB, wait_for=[])
    step1.job.spec.cluster_id = "the-only-cluster"

    step2 = MagicMock(name="step-b", type=V1PipelineStepType.DEPLOYMENT, wait_for=["step-a"])
    step2.deployment.spec.cluster_id = "the-only-cluster"

    test_printer = TestPrinter("my-single-cluster-pipeline", True, pipeline, teamspace, [step1, step2], schedules=[])
    test_printer.print_summary()
    output = test_printer.get_output_as_string()

    assert "Cloud account:" in output  # Note: singular, no "'s"
    assert "Cloud account's':" not in output
    assert "  - the-only-cluster" in output


def test_print_summary_with_no_steps():
    """Tests that the cloud account section is omitted when there are no steps."""
    pipeline = MagicMock(name="no-steps-pipeline")
    teamspace = MagicMock(name="test-team", owner=MagicMock(name="test-user"))

    test_printer = TestPrinter("no-steps-pipeline", True, pipeline, teamspace, proto_steps=[], schedules=[])
    test_printer.print_summary()
    output = test_printer.get_output_as_string()

    assert "Workflow Steps:" in output
    assert "  - No steps defined." in output
    # Assert that the entire "Cloud account" section is missing
    assert "Cloud account" not in output


def test_print_summary_updated():
    """Tests that the cloud account section is omitted when there are no steps."""
    pipeline = MagicMock(name="no-steps-pipeline")
    teamspace = MagicMock(name="test-team", owner=MagicMock(name="test-user"))

    test_printer = TestPrinter("update-pipeline", False, pipeline, teamspace, proto_steps=[], schedules=[])
    test_printer.print_summary()
    output = test_printer.get_output_as_string()

    assert "Pipeline 'update-pipeline' updated successfully!" in output
    assert "/pipelines/update-pipeline?app_id=pipeline" in output


def test_deployment_release_step():
    teamspace = MagicMock()
    step = DeploymentReleaseStep(deployment_name="prod", command="python server.py", ports=[8000], image="nginx")
    step_proto = step.to_proto(teamspace, "test-8", True)
    assert step_proto.deployment.name == "prod"
    assert step_proto.deployment.spec.image == "nginx"
    assert step_proto.deployment.spec.command == "python server.py"
    assert step_proto.deployment.spec.cluster_id == "test-8"
    assert step_proto.deployment.endpoint.ports == ["8000"]
