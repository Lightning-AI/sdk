import inspect
from unittest.mock import MagicMock

import pytest

from lightning_sdk import teamspace, user
from lightning_sdk.lightning_cloud.openapi.models import (
    ProjectIdJobsBody,
    V1JobSpec,
    V1PipelineStep,
    V1PipelineStepType,
)
from lightning_sdk.machine import Machine
from lightning_sdk.pipeline import Job, Pipeline
from lightning_sdk.pipeline import pipeline as pipeline_module
from lightning_sdk.pipeline.utils import DEFAULT, prepare_steps


def test_pipeline_run(monkeypatch):
    monkeypatch.setattr(pipeline_module, "Auth", MagicMock())
    monkeypatch.setattr(pipeline_module, "UserApi", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
    monkeypatch.setattr(teamspace, "TeamspaceApi", MagicMock())
    monkeypatch.setattr(pipeline_module, "_get_cluster", MagicMock())
    pipeline_api_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "PipelineApi", pipeline_api_mock)
    resolve_teamspace_mock = MagicMock()
    monkeypatch.setattr(pipeline_module, "_resolve_teamspace", resolve_teamspace_mock)

    pipeline = Pipeline(name="first-pipeline")

    with pytest.raises(ValueError, match="The step 0 requires a name"):
        pipeline.run(
            steps=[
                Job(
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
            ]
        )

    with pytest.raises(ValueError, match="You can only reference prior steps"):
        pipeline.run(
            steps=[
                Job(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
                Job(
                    name="job-1",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    needs=["job-1"],
                ),
            ]
        )

    with pytest.raises(ValueError, match="The step 1 doesn't have a valid needs. Found job-3"):
        pipeline.run(
            steps=[
                Job(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
                Job(
                    name="job-1",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    needs=["job-3"],
                ),
            ]
        )

    with pytest.raises(ValueError, match="You can only reference prior steps"):
        pipeline.run(
            steps=[
                Job(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
                Job(
                    name="job-1",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    needs=["job-2"],
                ),
                Job(
                    name="job-2",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                ),
            ]
        )

    pipeline.run(
        steps=[
            Job(
                name="job-0",
                machine=Machine.CPU,
                command="echo 'Hello, World!'",
                image="ubuntu:latest",
            ),
            Job(name="job-1", machine=Machine.CPU, command="echo 'Hello, World!'", image="ubuntu:latest", needs=None),
            Job(
                name="job-2",
                machine=Machine.CPU,
                command="echo 'Hello, World!'",
                image="ubuntu:latest",
            ),
        ]
    )

    args = pipeline_api_mock().create_pipeline._mock_mock_calls[0].args

    assert args[0] == "first-pipeline"

    generated = pipeline_api_mock().create_pipeline._mock_mock_calls[0].args[2]

    step_1 = V1PipelineStep(
        name="job-0",
        type=V1PipelineStepType.JOB,
        needs=[],
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
        needs=[],
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
        needs=["job-0", "job-1"],
        job=ProjectIdJobsBody(
            name="job-2",
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

    assert step_1 == generated[0]
    assert step_2 == generated[1]
    assert step_3 == generated[2]


def test_job_parameters_stay_in_sync():
    from lightning_sdk.job import Job
    from lightning_sdk.pipeline.types import Job as JobType

    job_signature = inspect.signature(Job.run)
    job_type_signature = inspect.signature(JobType.__init__)

    job_keys = job_signature.parameters.keys()
    job_type_keys = job_type_signature.parameters.keys()

    # ignore the depreceated parameters
    job_keys = [key for key in job_keys if key not in ["artifacts_local", "artifacts_remote", "cluster"]]
    job_type_keys = [key for key in job_type_keys if key not in ["needs", "self"]]

    assert sorted(job_keys) == sorted(job_type_keys)


def test_prepare_steps():
    steps = [
        V1PipelineStep(name="a", needs=DEFAULT),
        V1PipelineStep(name="b", needs=DEFAULT),
        V1PipelineStep(name="c", needs=DEFAULT),
        V1PipelineStep(name="d", needs=DEFAULT),
        V1PipelineStep(name="e", needs=DEFAULT),
    ]
    steps = prepare_steps(steps)
    assert steps[0].needs == []
    assert steps[1].needs == ["a"]
    assert steps[2].needs == ["b"]
    assert steps[3].needs == ["c"]
    assert steps[4].needs == ["d"]

    steps = [
        V1PipelineStep(name="a", needs=DEFAULT),
        V1PipelineStep(name="b", needs=[]),
        V1PipelineStep(name="c", needs=DEFAULT),
        V1PipelineStep(name="d", needs=DEFAULT),
        V1PipelineStep(name="e", needs=DEFAULT),
    ]
    steps = prepare_steps(steps)
    assert steps[0].needs == []
    assert steps[1].needs == []
    assert steps[2].needs == ["a", "b"]
    assert steps[3].needs == ["c"]
    assert steps[4].needs == ["d"]

    steps = [
        V1PipelineStep(name="a", needs=DEFAULT),
        V1PipelineStep(name="b", needs=[]),
        V1PipelineStep(name="c", needs=DEFAULT),
        V1PipelineStep(name="d", needs=[]),
        V1PipelineStep(name="e", needs=[]),
    ]
    steps = prepare_steps(steps)
    assert steps[0].needs == []
    assert steps[1].needs == []
    assert steps[2].needs == ["a", "b"]
    assert steps[3].needs == []
    assert steps[4].needs == []

    steps = [
        V1PipelineStep(name="a", needs=DEFAULT),
        V1PipelineStep(name="b", needs=[]),
        V1PipelineStep(name="c", needs=DEFAULT),
        V1PipelineStep(name="d", needs=[]),
        V1PipelineStep(name="e", needs=[]),
        V1PipelineStep(name="f", needs=DEFAULT),
    ]
    steps = prepare_steps(steps)
    assert steps[0].needs == []
    assert steps[1].needs == []
    assert steps[2].needs == ["a", "b"]
    assert steps[3].needs == []
    assert steps[4].needs == []
    assert steps[5].needs == ["c", "d", "e"]
