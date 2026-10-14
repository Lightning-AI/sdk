from typing import List
from unittest import mock

import pytest

from lightning_sdk.api.job_api import (
    JobApiV2,
    _match_accelerator,
)
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceUpdateJobBody,
    V1Job,
    V1JobSpec,
    V1PathMapping,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
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
        entrypoint="sh -c",
        path_mappings={"/output2": "data2:some-other-path", "/output": "data:some-path"},
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


def test_job_v2_submit_job_threads_placement_group_id(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        placement_group_id="pg-1",
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.spec.placement_group_id == "pg-1"


def test_job_v2_submit_job_threads_max_run_attempts(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        max_run_attempts=3,
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.spec.max_run_attempts == 3


def test_job_v2_submit_job_omits_unset_max_run_attempts(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.spec.max_run_attempts is None


def test_job_v2_submit_job_threads_keep_minutes(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        keep_minutes=30,
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.spec.reserve_machines_timeout_minutes == 30
    assert body.spec.keep_machine_after_stop is True


@pytest.mark.parametrize("timeout", [None, 0])
def test_job_v2_submit_job_omits_unset_keep_minutes(mocker_auth, timeout):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        keep_minutes=timeout,
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.spec.reserve_machines_timeout_minutes is None
    assert body.spec.keep_machine_after_stop is None


def test_job_v2_submit_job_rejects_negative_keep_minutes(mocker_auth):
    job_api = JobApiV2()
    job_api._client.jobs_service_create_job = mock.MagicMock()

    with pytest.raises(ValueError, match="keep_minutes must be >= 0"):
        job_api.submit_job(
            name="test-job",
            cloud_account="c-abc",
            teamspace_id="ts-abc",
            image="image-abc",
            studio_id="",
            machine=Machine.CPU,
            interruptible=False,
            env=None,
            command="echo hello",
            image_credentials=None,
            cloud_account_auth=False,
            entrypoint="sh -c",
            path_mappings=None,
            keep_minutes=-1,
        )


def test_job_v2_submit_job_threads_tags(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        tags=["prod", "team a"],
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.tags == ["prod", "team a"]


def test_job_v2_submit_job_omits_unset_tags(mocker_auth):
    job_api = JobApiV2()
    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock

    job_api.submit_job(
        name="test-job",
        cloud_account="c-abc",
        teamspace_id="ts-abc",
        image="image-abc",
        studio_id="",
        machine=Machine.CPU,
        interruptible=False,
        env=None,
        command="echo hello",
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint="sh -c",
        path_mappings=None,
        tags=[],
    )

    body = create_job_mock.call_args.kwargs["body"]
    assert body.tags is None


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
        ("creating", Status.Pending),
        ("running", Status.Running),
        ("restarting", Status.Running),
        ("stopping", Status.Stopping),
        ("stop", Status.Stopping),
        ("delete", Status.Stopping),
        ("stopped", Status.Stopped),
        ("deleted", Status.Stopped),
        ("complete", Status.Stopping),
        ("completed", Status.Completed),
        ("fail", Status.Stopping),
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
        (["fail", "failed"], 2, False),
        (["complete", "completed"], 2, False),
        (["stop", "stopped"], 2, False),
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


def test_match_accelerator_by_slug():
    accelerator = mock.MagicMock(
        slug="cpu-4",
        slug_multi_cloud="cpu-4",
        instance_id="m5.xlarge",
        secondary_instance_id=None,
    )
    assert _match_accelerator(Machine.CPU, [accelerator]) is accelerator
    assert _match_accelerator("gpu-unknown", [accelerator]) is None


def test_warn_if_max_runtime_noop_skips_when_unset():
    import warnings

    job_api = JobApiV2()
    job_api._get_machines_for_cloud_account = mock.MagicMock()
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        job_api.warn_if_max_runtime_noop(
            max_runtime=None,
            machine=Machine.CPU,
            interruptible=False,
            teamspace_id="ts",
            cloud_account_id="c",
            org_id="org",
        )
    assert recorded == []
    job_api._get_machines_for_cloud_account.assert_not_called()


def test_warn_if_max_runtime_noop_on_spot():
    job_api = JobApiV2()
    job_api._get_machines_for_cloud_account = mock.MagicMock()
    with pytest.warns(UserWarning, match="interruptible"):
        job_api.warn_if_max_runtime_noop(
            max_runtime=3600,
            machine=Machine.CPU,
            interruptible=True,
            teamspace_id="ts",
            cloud_account_id="c",
            org_id="org",
        )
    job_api._get_machines_for_cloud_account.assert_not_called()


def test_warn_if_max_runtime_noop_on_non_dws_machine():
    job_api = JobApiV2()
    job_api._get_machines_for_cloud_account = mock.MagicMock(
        return_value=[
            mock.MagicMock(
                slug="cpu-4",
                slug_multi_cloud="cpu-4",
                instance_id="m5.xlarge",
                secondary_instance_id=None,
                dws_supported=False,
                dws_only=False,
            )
        ]
    )
    with pytest.warns(UserWarning, match="no effect on machine"):
        job_api.warn_if_max_runtime_noop(
            max_runtime=3600,
            machine=Machine.CPU,
            interruptible=False,
            teamspace_id="ts",
            cloud_account_id="c",
            org_id="org",
        )


def test_warn_if_max_runtime_noop_on_baremetal_machine():
    job_api = JobApiV2()
    job_api._get_machines_for_cloud_account = mock.MagicMock(
        return_value=[
            mock.MagicMock(
                slug="lit-h200x-8",
                slug_multi_cloud="lit-h200x-8",
                instance_id="lit-h200x-8",
                secondary_instance_id=None,
                provider="MACHINE",
                dws_supported=False,
                dws_only=False,
            )
        ]
    )
    with pytest.warns(UserWarning, match="does not stop the job") as recorded:
        job_api.warn_if_max_runtime_noop(
            max_runtime=7200,
            machine="lit-h200x-8",
            interruptible=False,
            teamspace_id="ts",
            cloud_account_id="lightning-baremetal",
            org_id="org",
        )
    assert "timeout 7200" in str(recorded[0].message)
    assert not any("no effect" in str(warning.message) for warning in recorded)


def test_warn_if_max_runtime_noop_silent_for_dws_machine():
    import warnings

    job_api = JobApiV2()
    job_api._get_machines_for_cloud_account = mock.MagicMock(
        return_value=[
            mock.MagicMock(
                slug="h100",
                slug_multi_cloud="h100",
                instance_id="a3-highgpu-1g",
                secondary_instance_id=None,
                dws_supported=True,
                dws_only=False,
            )
        ]
    )
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        job_api.warn_if_max_runtime_noop(
            max_runtime=3600,
            machine="h100",
            interruptible=False,
            teamspace_id="ts",
            cloud_account_id="c",
            org_id="org",
        )
    assert recorded == []


def test_get_studio_name_returns_none_when_cloudspace_missing():
    job_api = JobApiV2()
    job_api._client.cloud_space_service_get_cloud_space = mock.MagicMock(
        side_effect=ApiException(status=404, reason="Not Found")
    )
    job = V1Job(project_id="ts-abc", spec=V1JobSpec(cloudspace_id="deleted-studio"))

    assert job_api.get_studio_name(job) is None
    job_api._client.cloud_space_service_get_cloud_space.assert_called_once_with(
        project_id="ts-abc", id="deleted-studio"
    )


def test_get_studio_name_reraises_non_404():
    job_api = JobApiV2()
    job_api._client.cloud_space_service_get_cloud_space = mock.MagicMock(
        side_effect=ApiException(status=500, reason="Internal Server Error")
    )
    job = V1Job(project_id="ts-abc", spec=V1JobSpec(cloudspace_id="studio-abc"))

    with pytest.raises(ApiException) as raised:
        job_api.get_studio_name(job)
    assert raised.value.status == 500


def test_get_studio_name_caches_cloudspace_lookups(mocker_auth):
    job_api_a = JobApiV2()
    job_api_b = JobApiV2()
    cs = mock.MagicMock()
    cs.name = "studio-a"
    get_cs = mock.MagicMock(return_value=cs)
    job_api_a._client.cloud_space_service_get_cloud_space = get_cs
    job = V1Job(project_id="ts-abc", spec=V1JobSpec(cloudspace_id="cs-1"))

    assert job_api_a.get_studio_name(job) == "studio-a"
    assert job_api_b.get_studio_name(job) == "studio-a"
    assert get_cs.call_count == 1
    assert JobApiV2._cached_studio_name.cache_info().hits == 1


def test_machine_from_spec_skips_accelerator_lookup_for_known_slug():
    job_api = JobApiV2()
    job_api._get_machines_for_cloud_account = mock.MagicMock()

    machine = job_api._get_job_machine_from_spec(
        V1JobSpec(instance_name="lit-t4-4", cluster_id="c-abc"), "ts-abc", "org-abc"
    )

    assert machine == Machine.T4_X_4
    job_api._get_machines_for_cloud_account.assert_not_called()


def test_rename_job_sends_request_and_returns_job(mocker_auth):
    job_api = JobApiV2()
    update_mock = mock.MagicMock()
    update_mock.return_value = V1Job(id="job-1", name="renamed-job", spec=V1JobSpec())
    job_api._client.jobs_service_update_job = update_mock

    result = job_api.rename_job(job_id="job-1", teamspace_id="ts-abc", new_name="renamed-job")

    assert result.name == "renamed-job"
    update_mock.assert_called_once_with(
        project_id="ts-abc",
        id="job-1",
        body=JobsServiceUpdateJobBody(name="renamed-job"),
    )


def test_set_tags_sends_request(mocker_auth):
    from lightning_sdk.lightning_cloud.openapi import JobsServiceSetWorkloadTagsBody

    job_api = JobApiV2()
    set_tags_mock = mock.MagicMock()
    job_api._client.jobs_service_set_workload_tags = set_tags_mock

    job_api.set_tags(job_id="job-1", teamspace_id="ts-abc", tags=["prod", "team a"])

    set_tags_mock.assert_called_once_with(
        project_id="ts-abc",
        workload_type="job",
        workload_id="job-1",
        body=JobsServiceSetWorkloadTagsBody(tags=["prod", "team a"]),
    )


def test_set_tags_sends_empty_list(mocker_auth):
    from lightning_sdk.lightning_cloud.openapi import JobsServiceSetWorkloadTagsBody

    job_api = JobApiV2()
    set_tags_mock = mock.MagicMock()
    job_api._client.jobs_service_set_workload_tags = set_tags_mock

    job_api.set_tags(job_id="job-1", teamspace_id="ts-abc", tags=[])

    set_tags_mock.assert_called_once_with(
        project_id="ts-abc",
        workload_type="job",
        workload_id="job-1",
        body=JobsServiceSetWorkloadTagsBody(tags=[]),
    )
