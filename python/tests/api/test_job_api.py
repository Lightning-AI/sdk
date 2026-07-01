from typing import List
from unittest import mock

import pytest

from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceUpdateJobBody,
    V1Job,
    V1JobSpec,
    V1PathMapping,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


def test_job_v2_submit_job(mocker_auth):
    from lightning_sdk.lightning_cloud.openapi import JobsServiceCreateJobBody, V1EnvVar, V1JobSpec

    job_api = JobApiV2()

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="",
        studio_id="st-abc",
        machine=Machine.T4_X_4,
        interruptible=False,
        env={"key": "value"},
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=True,
        artifacts_local=None,
        artifacts_remote=None,
        entrypoint="sh -c",
        path_mappings=None,
    )

    spec = V1JobSpec(
        cloudspace_id="st-abc",
        cluster_id="c-abc",
        command="echo hello",
        env=[V1EnvVar(name="key", value="value")],
        image="",
        instance_name="lit-t4-4",
        run_id=mock.ANY,
        spot=False,
        image_cluster_credentials=True,
        image_secret_ref="",
        entrypoint="sh -c",
        path_mappings=[],
        volumes=[],
    )
    body = JobsServiceCreateJobBody(name="test-job", spec=spec)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock
    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        studio_id="",
        image="image-abc",
        machine="some-dummy-instance-type",
        interruptible=True,
        env=None,
        command=None,
        image_credentials="dockerhub",
        cloud_account_auth=False,
        artifacts_local="/output",
        artifacts_remote="efs:data:some-path",
        entrypoint="sh -c",
        path_mappings={"/output2": "data2:some-other-path"},
    )

    spec = V1JobSpec(
        cloudspace_id="",
        cluster_id="c-abc",
        command="",
        env=[],
        image="image-abc",
        instance_name="some-dummy-instance-type",
        run_id=mock.ANY,
        spot=True,
        image_cluster_credentials=False,
        image_secret_ref="dockerhub",
        entrypoint="sh -c",
        path_mappings=[
            V1PathMapping(container_path="/output2", connection_name="data2", connection_path="some-other-path"),
            V1PathMapping(container_path="/output", connection_name="data", connection_path="some-path"),
        ],
        volumes=[],
    )
    body = JobsServiceCreateJobBody(name="test-job", spec=spec)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)


def test_get_job_by_name(mocker_auth):
    job_api = JobApiV2()

    get_job_by_name_mock = mock.MagicMock()
    job_api._client.jobs_service_find_job = get_job_by_name_mock

    job_api.get_job_by_name("test-job", "ts-abc")
    get_job_by_name_mock.assert_called_once_with(name="test-job", project_id="ts-abc")


def test_get_job_v2(mocker_auth):
    job_api = JobApiV2()

    get_job_mock = mock.MagicMock()
    job_api._client.jobs_service_get_job = get_job_mock

    job_api.get_job("test-job-id", "ts-abc")
    get_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc")


@pytest.mark.parametrize(
    ("internal_state", "expected_state"),
    [
        ("pending", Status.Pending),
        ("running", Status.Running),
        ("stopped", Status.Stopped),
        ("completed", Status.Completed),
        ("failed", Status.Failed),
        ("unknown", Status.Pending),
    ],
)
def test_translate_state(mocker_auth, internal_state, expected_state):
    job_api = JobApiV2()
    assert job_api._job_state_to_external(internal_state) == expected_state


@pytest.mark.parametrize(
    ("instance_name", "instance_type", "expected_machine"),
    [
        ("g4dn.12xlarge", None, Machine.T4_X_4),
        ("p4d.24xlarge", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "", Machine("unknown", "unknown")),
        ("", "unknown", Machine("unknown", "unknown")),
    ],
)
def test_machine_translate(
    mocker_auth, internal_studio_api_mocker_get_machine, instance_name, instance_type, expected_machine
):
    job_api = JobApiV2()

    spec = V1JobSpec(
        instance_name=instance_name,
        instance_type=instance_type,
        cluster_id="cluster_abc",
    )

    assert job_api._get_job_machine_from_spec(spec, teamspace_id="my-teamspace", org_id="test-org") == expected_machine


@pytest.mark.parametrize(
    ("job_states", "total_calls_get_job", "called_update_job"),
    [
        (["running", "stopped"], 2, True),
        (["running", "completed"], 2, True),
        (["stopped"], 1, False),
        (["completed"], 1, False),
        (["failed"], 1, False),
        (["pending", "stopped"], 2, True),
        (["pending", "running", "stopped"], 3, True),
        (["stopping", "stopping", "stopping", "stopped"], 4, False),
    ],
)
def test_jobv2_stop(mocker_auth, job_states: List[str], total_calls_get_job: int, called_update_job: bool):
    job_api = JobApiV2()

    def get_job_side_effect(*args, **kwargs):
        while job_states:
            return V1Job(id="test-job-id", state=job_states.pop(0), spec=V1JobSpec(cloudspace_id="cloudspace-id"))

        return V1Job(id="test-job-id", state="stopped", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job_api._client.jobs_service_get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job_api._client.jobs_service_update_job = update_job_mock

    job_api.stop_job("test-job-id", "ts-abc")

    assert get_job_mock.call_count == total_calls_get_job

    if called_update_job:
        update_job_mock.assert_called_once_with(
            id="test-job-id", project_id="ts-abc", body=JobsServiceUpdateJobBody(state="stop")
        )
    else:
        update_job_mock.assert_not_called()


@pytest.mark.parametrize(
    ("cloudspace_id", "expected_cloudspace_id"), [(None, ""), ("cloudspace-id", "cloudspace-id"), ("", "")]
)
def test_jobv2_delete(mocker_auth, cloudspace_id, expected_cloudspace_id):
    job_api = JobApiV2()

    delete_job_mock = mock.MagicMock()
    job_api._client.jobs_service_delete_job = delete_job_mock

    job_api.delete_job("test-job-id", "ts-abc", cloudspace_id)

    delete_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc", cloudspace_id=expected_cloudspace_id)
