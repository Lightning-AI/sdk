from typing import List
from unittest import mock

import pytest

from lightning_sdk.api.mmt_api import MMTApiV1, MMTApiV2

try:
    from lightning_sdk.lightning_cloud.openapi import AppsIdBody1 as AppsIdBody
except ImportError:
    from lightning_sdk.lightning_cloud.openapi import AppsIdBody
from lightning_sdk.lightning_cloud.openapi import (
    MultimachinejobsIdBody,
    ProjectIdMultimachinejobsBody,
    V1EnvVar,
    V1JobSpec,
    V1MultiMachineJob,
    V1PathMapping,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status


def test_mmt_v1_submit_job():
    job_api = MMTApiV1()

    create_job_mock = mock.MagicMock()
    job_api._client.cloud_space_service_create_cloud_space_app_instance = create_job_mock

    job_api.submit_job(
        name="test-job",
        num_machines=5,
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        studio_id="st-abc",
        machine=Machine.T4_X_4,
        interruptible=False,
        command="echo hello",
        strategy="parallel",
    )

    body = AppsIdBody(
        cluster_id="c-abc",
        plugin_arguments={
            "distributedArguments": '{"cloud_compute": '
            '"lit-t4-4", '
            '"num_instances": 5, "strategy": '
            '"parallel"}',
            "entrypoint": "echo hello",
            "name": "test-job",
            "spot": "false",
        },
        unique_id=mock.ANY,
    )

    create_job_mock.assert_called_once_with(
        body=body, project_id="ts-abc", cloudspace_id="st-abc", id="distributed_plugin"
    )

    create_job_mock = mock.MagicMock()
    job_api._client.cloud_space_service_create_cloud_space_app_instance = create_job_mock

    job_api.submit_job(
        name="test-job",
        num_machines=5,
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        studio_id="st-abc",
        machine="some-dummy-machine",
        interruptible=False,
        command="echo hello",
        strategy="parallel",
    )

    body = AppsIdBody(
        cluster_id="c-abc",
        plugin_arguments={
            "distributedArguments": '{"cloud_compute": '
            '"some-dummy-machine", '
            '"num_instances": 5, "strategy": '
            '"parallel"}',
            "entrypoint": "echo hello",
            "name": "test-job",
            "spot": "false",
        },
        unique_id=mock.ANY,
    )

    create_job_mock.assert_called_once_with(
        body=body, project_id="ts-abc", cloudspace_id="st-abc", id="distributed_plugin"
    )


def test_mmt_v2_submit_job():
    job_api = MMTApiV2()

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_multi_machine_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        num_machines=5,
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
        max_runtime=None,
    )

    spec = V1JobSpec(
        cloudspace_id="st-abc",
        cluster_id="c-abc",
        command="echo hello",
        env=[V1EnvVar(name="key", value="value")],
        image="",
        entrypoint="sh -c",
        instance_name="lit-t4-4",
        run_id=mock.ANY,
        spot=False,
        image_cluster_credentials=True,
        image_secret_ref="",
        path_mappings=[],
    )
    body = ProjectIdMultimachinejobsBody(name="test-job", spec=spec, cluster_id="c-abc", machines=5)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_multi_machine_job = create_job_mock
    job_api.submit_job(
        name="test-job",
        num_machines=2,
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        studio_id="",
        image="image-abc",
        machine="some-dummy-machine",
        interruptible=True,
        env=None,
        command=None,
        image_credentials="dockerhub",
        cloud_account_auth=False,
        artifacts_local="/output",
        artifacts_remote="efs:data:some-path",
        entrypoint="sh -c",
        path_mappings={"/output2": "data2:some-other-path"},
        max_runtime=500,
    )

    spec = V1JobSpec(
        cloudspace_id="",
        cluster_id="c-abc",
        command="",
        env=[],
        image="image-abc",
        entrypoint="sh -c",
        instance_name="some-dummy-machine",
        run_id=mock.ANY,
        spot=True,
        image_cluster_credentials=False,
        image_secret_ref="dockerhub",
        path_mappings=[
            V1PathMapping(container_path="/output2", connection_name="data2", connection_path="some-other-path"),
            V1PathMapping(container_path="/output", connection_name="data", connection_path="some-path"),
        ],
        requested_run_duration_seconds="500",
    )
    body = ProjectIdMultimachinejobsBody(name="test-job", spec=spec, cluster_id="c-abc", machines=2)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)


def test_get_mmt_by_name():
    job_api = MMTApiV2()

    get_job_by_name_mock = mock.MagicMock()
    job_api._client.jobs_service_get_multi_machine_job_by_name = get_job_by_name_mock

    job_api.get_job_by_name("test-job", "ts-abc")
    get_job_by_name_mock.assert_called_once_with(name="test-job", project_id="ts-abc")


def test_get_mmt():
    job_api = MMTApiV2()

    get_job_mock = mock.MagicMock()
    job_api._client.jobs_service_get_multi_machine_job = get_job_mock

    job_api.get_job("test-job-id", "ts-abc")
    get_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc")


@pytest.mark.parametrize(
    ("internal_state", "expected_state"),
    [
        ("MultiMachineJob_STATE_UNSPECIFIED", Status.Pending),
        ("MultiMachineJob_STATE_RUNNING", Status.Running),
        ("MultiMachineJob_STATE_STOPPED", Status.Stopped),
        ("MultiMachineJob_STATE_FAILED", Status.Failed),
        ("MultiMachineJob_STATE_COMPLETED", Status.Completed),
    ],
)
def test_translate_state(internal_state, expected_state):
    job_api = MMTApiV2()
    assert job_api._job_state_to_external(internal_state) == expected_state


@pytest.mark.parametrize(
    ("instance_name", "instance_type", "expected_machine"),
    [
        ("g4dn.12xlarge", None, Machine.T4_X_4),
        ("p4d.24xlarge", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "", Machine.from_str("unknown")),
        ("", "unknown", Machine.from_str("unknown")),
    ],
)
def test_machine_translate(
    mocker_auth, internal_studio_api_mocker_get_machine, instance_name, instance_type, expected_machine
):
    job_api = MMTApiV2()

    spec = V1JobSpec(
        instance_name=instance_name,
        instance_type=instance_type,
        cluster_id="cluster_abc",
    )

    assert job_api._get_job_machine_from_spec(spec) == expected_machine


@pytest.mark.parametrize(
    ("job_states", "total_calls_get_job", "called_update_job"),
    [
        (["MultiMachineJob_STATE_RUNNING", "MultiMachineJob_STATE_STOPPED"], 2, True),
        (["MultiMachineJob_STATE_RUNNING", "MultiMachineJob_STATE_COMPLETED"], 2, True),
        (["MultiMachineJob_STATE_RUNNING", "MultiMachineJob_STATE_FAILED"], 2, True),
        (["MultiMachineJob_STATE_STOPPED"], 1, False),
        (["MultiMachineJob_STATE_COMPLETED"], 1, False),
        (["MultiMachineJob_STATE_FAILED"], 1, False),
        (["MultiMachineJob_STATE_UNSPECIFIED", "MultiMachineJob_STATE_STOPPED"], 2, True),
        (
            ["MultiMachineJob_STATE_UNSPECIFIED", "MultiMachineJob_STATE_RUNNING", "MultiMachineJob_STATE_STOPPED"],
            3,
            True,
        ),
    ],
)
def test_mmt_stop(job_states: List[str], total_calls_get_job: int, called_update_job: bool):
    job_api = MMTApiV2()

    def get_job_side_effect(*args, **kwargs):
        while job_states:
            state = job_states.pop(0)
            return V1MultiMachineJob(
                id="test-job-id", desired_state=state, spec=V1JobSpec(cloudspace_id="cloudspace-id"), state=state
            )

        return V1MultiMachineJob(
            id="test-job-id",
            desired_state="MultiMachineJob_STATE_STOPPED",
            state="MultiMachineJob_STATE_STOPPED",
            spec=V1JobSpec(cloudspace_id="cloudspace-id"),
        )

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job_api._client.jobs_service_get_multi_machine_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job_api._client.jobs_service_update_multi_machine_job = update_job_mock

    job_api.stop_job("test-job-id", "ts-abc")

    assert get_job_mock.call_count == total_calls_get_job

    if called_update_job:
        update_job_mock.assert_called_once_with(
            id="test-job-id",
            project_id="ts-abc",
            body=MultimachinejobsIdBody(desired_state="MultiMachineJob_STATE_STOP"),
        )
    else:
        update_job_mock.assert_not_called()


def test_mmt_delete():
    job_api = MMTApiV2()

    delete_job_mock = mock.MagicMock()
    job_api._client.jobs_service_delete_multi_machine_job = delete_job_mock

    job_api.delete_job("test-job-id", "ts-abc")

    delete_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc")
