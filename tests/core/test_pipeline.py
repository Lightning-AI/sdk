import inspect
from unittest.mock import MagicMock

import pytest

from lightning_sdk import teamspace, user
from lightning_sdk.api import pipeline_api
from lightning_sdk.lightning_cloud.openapi.models import (
    ProjectIdJobsBody,
    V1JobSpec,
    V1PipelineStep,
    V1PipelineStepType,
)
from lightning_sdk.machine import Machine
from lightning_sdk.pipeline import MMT, Deployment, Job, Pipeline
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

    pipeline = Pipeline(name="first-pipeline", org="org", user="user")
    cloud_account_mock = MagicMock()
    cloud_account_mock.cluster_id = ""
    pipeline._cloud_account = cloud_account_mock

    assert resolve_teamspace_mock._mock_mock_calls[0].kwargs["org"] == "org"
    assert resolve_teamspace_mock._mock_mock_calls[0].kwargs["user"] == "user"

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
                    wait_for=["job-1"],
                ),
            ]
        )

    with pytest.raises(ValueError, match="The step 1 doesn't have a valid wait_for. Found job-3"):
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
                    wait_for=["job-3"],
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
                    wait_for=["job-2"],
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
            Job(
                name="job-1", machine=Machine.CPU, command="echo 'Hello, World!'", image="ubuntu:latest", wait_for=None
            ),
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
    deployment = Deployment(machine=Machine.CPU)
    assert deployment.replicas == 1
    assert deployment.autoscale.min_replicas == 0
    assert deployment.autoscale.max_replicas == 1
    assert deployment.autoscale.target_metrics[0].name == "CPU"
    assert deployment.autoscale.target_metrics[0].target == 80

    deployment = Deployment(machine=Machine.A10G)
    assert deployment.autoscale.target_metrics[0].name == "GPU"


def test_mmt():
    mmt = MMT(name="mmt-0", machine=Machine.CPU)
    proto = mmt.to_proto(MagicMock(), "", False)
    assert proto.type == V1PipelineStepType.MMT
    assert proto.name == "mmt-0"
    assert proto.mmt is not None
    assert proto.job is None
    assert proto.deployment is None
    assert proto.mmt.machines == 2
    assert proto.mmt.spec.instance_name == "cpu-4"


def test_stop(monkeypatch):
    monkeypatch.setattr(pipeline_module, "Auth", MagicMock())
    monkeypatch.setattr(pipeline_module, "UserApi", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
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
    monkeypatch.setattr(pipeline_module, "Auth", MagicMock())
    monkeypatch.setattr(pipeline_module, "UserApi", MagicMock())
    monkeypatch.setattr(user, "UserApi", MagicMock())
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
    cloud_account_mock = MagicMock()
    cloud_account_mock.cluster_id = "cluster_id_1"
    pipeline._cloud_account = cloud_account_mock

    pipeline.run(
        steps=[
            Job(
                name="job-0",
                machine=Machine.CPU,
                command="echo 'Hello, World!'",
                image="ubuntu:latest",
                cloud_account="cluster_id_2",
            ),
        ]
    )

    assert len(pipeline_api_mock().create_pipeline._mock_mock_calls[0].args)
    assert pipeline_api_mock().create_pipeline._mock_mock_calls[0].args[-1] is False

    pipeline._shared_filesystem = True

    with pytest.raises(
        ValueError,
        match="With shared filesystem enabled, all the pipeline steps wait_for to be on the same cluster. Found cluster_id_1 and cluster_id_2",  # noqa: E501
    ):
        pipeline.run(
            steps=[
                Job(
                    name="job-0",
                    machine=Machine.CPU,
                    command="echo 'Hello, World!'",
                    image="ubuntu:latest",
                    cloud_account="cluster_id_2",
                ),
            ]
        )
