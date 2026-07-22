import os
from unittest import mock

import pytest

from lightning_sdk.job import Job
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceUpdateJobBody,
    V1Job,
    V1JobSpec,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_init(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_api_mocker_get_job_status_v2,
):
    job = Job("j-abc", "ts-abc", org="org-abc")
    assert isinstance(job._job, V1Job)

    assert isinstance(job.teamspace, Teamspace)
    assert job.teamspace.name == "ts-abc"


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_init_error(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_api_mocker_get_job_status_v2,
):
    def init_job_error():
        studio = Studio("st-abc", "ts-abc", org="org-abc")
        Job("xyz", studio.teamspace)

    with pytest.raises(ValueError, match="Job xyz does not exist in Teamspace ts-abc"):
        init_job_error()


@mock.patch.dict(os.environ, clear=True)
@pytest.mark.parametrize(
    ("name", "expected_status"),
    [
        ("j-abc", Status.Pending),  # None
        ("j-def", Status.Pending),  # "unknown"
        ("j-ghi", Status.Pending),  # "pending"
        ("j-jkl", Status.Running),  # "running"
        ("j-mno", Status.Failed),  # "failed"
        ("j-pqr", Status.Stopped),  # "stopped"
        ("j-stu", Status.Completed),  # "completed"
    ],
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_status(
    internal_job_api_mocker_get_job_status_v2,
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    name,
    expected_status,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")
    job = Job(name, studio.teamspace)
    job._job.name = name
    status = job.status
    assert isinstance(status, Status)

    assert status == expected_status


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_stop_job(
    internal_job_api_mocker_stop_job,
    internal_studio_init_mocker,
    internal_studio_status_mocker,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")

    job = Job("j-abc", studio.teamspace)
    status = job.status

    assert status == Status.Running
    job.stop()
    status = job.status
    assert status == Status.Stopped


@mock.patch.dict(os.environ, clear=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_delete_job(
    internal_job_api_mocker_delete_job_v2,
    internal_studio_init_mocker,
    internal_studio_status_mocker,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")
    job = Job("j-abc", studio.teamspace)

    job.delete()

    with pytest.raises(RuntimeError, match="Job j-abc does not exist in Teamspace ts-abc. Did you delete it?"):
        job.status  # noqa: B018

    with pytest.raises(ValueError, match="Job j-abc does not exist in Teamspace ts-abc"):
        Job("j-abc", studio.teamspace)


@pytest.mark.parametrize("machine", [Machine.CPU, Machine.T4_X_4])
@pytest.mark.parametrize("command", [None, "echo hello"])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_job_v2_image(internal_studio_init_mocker, machine, command, env, interruptible):
    teamspace = Teamspace("ts-abc", org="org-abc")
    job = Job("test-job", teamspace, _fetch_job=False)

    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock

    job._submit(
        machine=machine,
        image="image-abc",
        command=command,
        env=env,
        interruptible=interruptible,
        cloud_account="c-abc",
    )

    # test that everything was passed along correctly to the api layer and
    # that class values and function params are mixed correctly
    submit_mock.assert_called_once_with(
        name="test-job",
        command=command,
        cloud_account="c-abc",
        teamspace_id="ts-abc001",
        studio_id=None,
        image="image-abc",
        machine=machine,
        interruptible=interruptible,
        env=env,
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint=None,
        path_mappings=None,
        max_runtime=None,
        reuse_snapshot=True,
        scratch_disks=None,
        placement_group_id=None,
    )


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_exposes_private_provisioning_metadata(internal_studio_init_mocker):
    teamspace = Teamspace("ts-abc", org="org-abc")
    job = Job("test-job", teamspace, _fetch_job=False)
    job._job = V1Job(
        id="job-123",
        name="test-job",
        private_ip_address="10.0.0.7",
        spec=V1JobSpec(placement_group_id="pg-1", rank=3),
    )

    assert job.resource_id == "job-123"
    assert job.private_ip_address == "10.0.0.7"
    assert job.placement_group_id == "pg-1"
    assert job.rank == 3


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_job_threads_placement_group_id(internal_studio_init_mocker):
    teamspace = Teamspace("ts-abc", org="org-abc")
    job = Job("test-job", teamspace, _fetch_job=False)
    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock

    job._submit(
        machine=Machine.CPU,
        image="image-abc",
        command="echo hello",
        cloud_account="c-abc",
        placement_group_id="pg-1",
    )

    assert submit_mock.call_args.kwargs["placement_group_id"] == "pg-1"


@pytest.mark.parametrize("machine", [Machine.L4, Machine.DATA_PREP_MAX])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_job_v2_studio(internal_studio_init_mocker, machine, env, interruptible):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace, _fetch_job=False)
    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock
    job._submit(
        machine=machine,
        cloud_account=studio.cloud_account,
        studio=studio,
        env=env,
        interruptible=interruptible,
        command="echo hello",
    )

    submit_mock.assert_called_once_with(
        name="test-job",
        command="echo hello",
        cloud_account="c-abc",
        teamspace_id="ts-abc001",
        studio_id="st-abc",
        image=None,
        machine=machine,
        interruptible=interruptible,
        env=env,
        image_credentials=None,
        cloud_account_auth=False,
        entrypoint=None,
        path_mappings=None,
        max_runtime=None,
        reuse_snapshot=True,
        scratch_disks=None,
        placement_group_id=None,
    )


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_run_arg_validation(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    with pytest.raises(
        ValueError,
        match="Studio teamspace does not match provided teamspace."
        " Can only run jobs with Studio envs in the teamspace of that Studio.",
    ):
        Job.run("some name", Machine.CPU, command="some command", studio=studio, teamspace="other teamspace")

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        Job.run("", Machine.CPU)

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        Job.run(None, Machine.CPU)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_run_entrypoint_validation(internal_studio_init_mocker):
    """Test entrypoint validation logic for image jobs."""
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    # Test that empty string entrypoint is converted to None (use container default)
    submit_mock = mock.MagicMock()
    with mock.patch.object(Job, "_submit", submit_mock), mock.patch.object(
        Job, "link", new_callable=mock.PropertyMock, return_value="https://example.com/job"
    ):
        Job.run(
            "test-job",
            Machine.CPU,
            command="echo hello",
            image="alpine:latest",
            teamspace=studio.teamspace,
            entrypoint="",
        )
        submit_mock.assert_called_once()
        assert submit_mock.call_args.kwargs["entrypoint"] is None

    # Test that when command is provided with default entrypoint, sh -c is used
    submit_mock.reset_mock()
    with mock.patch.object(Job, "_submit", submit_mock), mock.patch.object(
        Job, "link", new_callable=mock.PropertyMock, return_value="https://example.com/job"
    ):
        Job.run(
            "test-job",
            Machine.CPU,
            command="echo hello",
            image="alpine:latest",
            teamspace=studio.teamspace,
        )
        submit_mock.assert_called_once()
        assert submit_mock.call_args.kwargs["entrypoint"] == "sh -c"

    # Test that no command with empty entrypoint uses container defaults
    submit_mock.reset_mock()
    with mock.patch.object(Job, "_submit", submit_mock), mock.patch.object(
        Job, "link", new_callable=mock.PropertyMock, return_value="https://example.com/job"
    ):
        Job.run(
            "test-job",
            Machine.CPU,
            command=None,
            image="alpine:latest",
            teamspace=studio.teamspace,
            entrypoint="",
        )
        submit_mock.assert_called_once()
        assert submit_mock.call_args.kwargs["entrypoint"] is None
        assert submit_mock.call_args.kwargs["command"] is None

    # Test that studio jobs raise error when entrypoint is specified
    with pytest.raises(ValueError, match="Specifying the entrypoint has no effect for jobs with Studio envs."):
        Job.run(
            "test-job",
            Machine.CPU,
            command="echo hello",
            studio=studio,
            entrypoint="/bin/bash -c",
        )


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_jobv2_error_cases(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace, _fetch_job=False)

    with pytest.raises(
        ValueError, match="image and studio are mutually exclusive as both define the environment to run the job in"
    ):
        job._submit(
            machine=Machine.T4_X_4,
            studio=studio,
            image="image-abc",
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
        )

    with pytest.raises(ValueError, match="command is required when using a studio"):
        job._submit(
            machine=Machine.T4_X_4,
            studio=studio,
            image=None,
            command=None,
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
        )

    with pytest.raises(ValueError, match="either image or studio must be provided"):
        job._submit(
            machine=Machine.T4_X_4,
            studio=None,
            image=None,
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
        )

    with pytest.raises(ValueError, match="scratch_disks are only supported within a studio job"):
        job._submit(
            machine=Machine.T4_X_4,
            image="alpine:latest",
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
            scratch_disks={"data": 100},
        )

    with pytest.raises(ValueError, match="scratch_disk size cannot exceed 50TiB"):
        job._submit(
            machine=Machine.T4_X_4,
            studio=studio,
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
            scratch_disks={"data": 50001},
        )

    with pytest.raises(ValueError, match="scratch_disk paths must be relative to /teamspace/scratch"):
        job._submit(
            machine=Machine.T4_X_4,
            studio=studio,
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
            scratch_disks={"/data": 100},
        )

    with pytest.raises(ValueError, match="scratch_disk path cannot contain '..'"):
        job._submit(
            machine=Machine.T4_X_4,
            studio=studio,
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
            scratch_disks={"/teamspace/scratch/../data": 100},
        )

    with pytest.raises(ValueError, match="scratch_disk may only contain up to 5 elements"):
        job._submit(
            machine=Machine.T4_X_4,
            studio=studio,
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
            scratch_disks={
                "a": 100,
                "b": 100,
                "c": 100,
                "d": 100,
                "e": 100,
                "f": 100,
            },
        )


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_job_by_name(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace, _fetch_job=False)

    job._job_api.get_job_by_name = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer
    # and that class values and function params are mixed correctly
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_job_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace, _fetch_job=False)

    # simulate updating internal job
    job._job = V1Job(id="test-job-id")

    job._job_api.get_job = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer and that class values
    # and function params are mixed correctly
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_job_by_name_first_and_then_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace, _fetch_job=False)
    job._job_api.get_job_by_name = mock.MagicMock()

    job._job_api.get_job = mock.MagicMock()

    job._update_internal_job()
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")

    # simulate updating internal job
    job._job = V1Job(id="test-job-id")

    job._update_internal_job()
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_job_by_name_on_init(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace)

    assert hasattr(job, "_job")
    assert job._job is not None

    assert job._job.id == "test-job-id"


@pytest.mark.parametrize(
    ("internal_status", "external_status"),
    [
        ("pending", Status.Pending),
        ("running", Status.Running),
        ("completed", Status.Completed),
        ("failed", Status.Failed),
        ("stopped", Status.Stopped),
    ],
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_status(job_api_get_job_by_name_mocker, internal_studio_init_mocker, internal_status, external_status):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1Job(id="test-job-id", state=internal_status)
    job._job_api.get_job = get_job_mock

    assert job.status == external_status
    get_job_mock.assert_called_once()


@pytest.mark.parametrize(
    ("internal_instance_name", "internal_instance_type", "expected_machine"),
    [
        ("g4dn.12xlarge", None, Machine.T4_X_4),
        ("p4d.24xlarge", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "", Machine.from_str("unknown")),
        ("", "unknown", Machine.from_str("unknown")),
    ],
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_machine(
    internal_studio_init_mocker,
    internal_studio_api_mocker_get_machine,
    internal_instance_name,
    internal_instance_type,
    expected_machine,
):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace, _fetch_job=False)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1Job(
        id="test-job-id",
        spec=V1JobSpec(
            instance_name=internal_instance_name, instance_type=internal_instance_type, cluster_id="cluster_abc"
        ),
    )
    job._job_api.get_job_by_name = get_job_mock

    assert job.machine == expected_machine
    get_job_mock.assert_called_once()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_stop(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace)

    i = 0

    def get_job_side_effect(*args, **kwargs):
        nonlocal i
        if i < 5:
            i += 1
            return V1Job(id="test-job-id", state="running", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

        return V1Job(id="test-job-id", state="stopped", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job._job_api.get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job._job_api._client.jobs_service_update_job = update_job_mock

    job.stop()

    assert get_job_mock.call_count == 6
    update_job_mock.assert_called_once_with(
        id="test-job-id", project_id="ts-abc001", body=JobsServiceUpdateJobBody(state="stop")
    )


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_delete(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job(
        "test-job",
        studio.teamspace,
    )

    delete_job_mock = mock.MagicMock()
    job._job_api.delete_job = delete_job_mock

    job.delete()

    delete_job_mock.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001", cloudspace_id="st-abc")


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_jobv2_studio_resolve(
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_studio_init_mocker,
    internal_job_get_cloudspace_mocker,
    job_api_get_job_by_name_mocker,
):
    from lightning_sdk.job import Job

    submit_mock = mock.MagicMock()
    Job._submit = submit_mock

    Job.run("test-job", machine=Machine.CPU, command="echo hello", studio="st-abc", teamspace="ts-abc", org="org-abc")

    submit_mock.assert_called_once_with(
        command="echo hello",
        cloud_account="c-abc",
        env=None,
        image=None,
        interruptible=False,
        machine=Machine.CPU,
        studio=Studio(name="st-abc", teamspace="ts-abc", org="org-abc"),
        cloud_account_auth=False,
        cloud=None,
        image_credentials=None,
        entrypoint=None,
        path_mappings=None,
        max_runtime=None,
        reuse_snapshot=True,
        scratch_disks=None,
        placement_group_id=None,
    )


@pytest.mark.parametrize(
    (
        "expected_artifacts_path",
        "expected_snapshot_path",
        "image",
        "studio",
        "artifacts_source",
        "artifacts_destination",
    ),
    [
        ("/teamspace/jobs/test-job/artifacts", "/teamspace/jobs/test-job/snapshot", None, "st-abc", None, None),
        ("/teamspace/efs_connections/data/some-path", None, "ubuntu", None, "/output", "efs:data:some-path"),
        (None, None, "ubuntu", None, None, None),
    ],
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_jobv2_studio_path(
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_studio_init_mocker,
    internal_job_get_cloudspace_mocker,
    job_api_get_job_by_name_mocker,
    expected_artifacts_path,
    expected_snapshot_path,
    image,
    studio,
    artifacts_source,
    artifacts_destination,
):
    from lightning_sdk.job import Job

    job = Job("test-job", Teamspace("ts-abc", org="org-abc"), _fetch_job=False)

    job._job = V1Job(
        name="test-job",
        spec=V1JobSpec(
            image=image or "", artifacts_source=artifacts_source, artifacts_destination=artifacts_destination
        ),
    )

    assert job.artifact_path == expected_artifacts_path
    assert job.snapshot_path == expected_snapshot_path


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_job_v2_image_from_studio(
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_studio_init_mocker,
    internal_job_get_cloudspace_mocker,
    job_api_get_job_by_name_mocker,
):
    from lightning_sdk.api.studio_api import StudioApi
    from lightning_sdk.job import Job

    submit_mock = mock.MagicMock()
    Job._submit = submit_mock
    keeping_alive_mock = mock.MagicMock()
    StudioApi.start_keeping_alive = keeping_alive_mock

    with mock.patch.dict(
        os.environ,
        {
            "LIGHTNING_CLOUD_SPACE_ID": "st-abc",
            "LIGHTNING_CLOUD_PROJECT_ID": "ts-abc001",
            "LIGHTNING_INTERACTIVE": "true",
        },
    ):
        Job.run(
            "test-job",
            machine=Machine.CPU,
            command="echo hello",
            studio=None,
            image="ubuntu",
            teamspace="ts-abc",
            org="org-abc",
        )

    submit_mock.assert_called_once_with(
        command="echo hello",
        cloud_account="c-abc",  # cloud account is inferred from studio we submit from
        env=None,
        image="ubuntu",
        interruptible=False,
        machine=Machine.CPU,
        studio=None,
        cloud_account_auth=False,
        cloud=None,
        image_credentials=None,
        entrypoint="sh -c",
        path_mappings=None,
        max_runtime=None,
        reuse_snapshot=True,
        scratch_disks=None,
        placement_group_id=None,
    )
    assert keeping_alive_mock.call_count == 0


@mock.patch("lightning_sdk.studio._internal_status_to_external_status", return_value=Status.Running)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_run_job_with_cloud_provider(
    mock_in_studio,
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_job_get_cloudspace_mocker,
    job_api_get_job_by_name_mocker,
):
    from lightning_sdk.job import Job

    submit_mock = mock.MagicMock()
    Job._submit = submit_mock

    Job.run(
        "test-job",
        machine=Machine.CPU,
        command="echo hello",
        image="nginx",
        teamspace="ts-abc",
        org="org-abc",
        cloud="nebius",
    )

    submit_mock.assert_called_once_with(
        command="echo hello",
        cloud_account=None,  # cloud_account still None
        env=None,
        image="nginx",
        interruptible=False,
        machine=Machine.CPU,
        studio=None,
        cloud_account_auth=False,
        cloud="nebius",
        image_credentials=None,
        entrypoint="sh -c",
        path_mappings=None,
        max_runtime=None,
        reuse_snapshot=True,
        scratch_disks=None,
        placement_group_id=None,
    )


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_logs_v2(
    internal_job_logs_mocker,
    job_api_get_job_by_name_mocker,
    internal_studio_init_mocker,
    job_api_get_job_by_id_mocker,
):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job(
        "test-job",
        studio.teamspace,
    )

    assert job.logs == "⚡  ~ echo Hello\nHello\n"


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_v2_dict_json(internal_studio_init_mocker, internal_studio_api_mocker_get_machine):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    internal_job = V1Job(
        name="my-job",
        project_id="ts-abc",
        spec=V1JobSpec(cloudspace_id="st-abc", command="some command", instance_type="cpu-4"),
        state="running",
        total_cost=3.51,
    )

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = internal_job
    get_studio_name_mock = mock.MagicMock()
    get_studio_name_mock.return_value = studio.name
    job = Job("my-job", teamspace=studio.teamspace, _fetch_job=False)
    job._job = internal_job
    job._update_internal_job = get_job_mock
    job._job_api.get_studio_name = get_studio_name_mock

    job_dict = job.dict()

    assert job_dict["name"] == "my-job"
    assert job_dict["teamspace"] == "org-abc/ts-abc"
    assert job_dict["studio"] == "st-abc"
    assert job_dict["image"] is None
    assert job_dict["command"] == "some command"
    assert job_dict["status"] == Status.Running
    assert job_dict["machine"] == Machine.CPU
    assert job_dict["total_cost"] == 3.51

    assert job.json() == (
        '{\n    "command": "some command",\n    "image": null,\n    "machine": "CPU",\n    '
        '"name": "my-job",\n    "status": "Running",\n    "studio": "st-abc",\n    "teamspace": "org-abc/ts-abc",\n    '
        '"total_cost": 3.51\n}'
    )


@pytest.mark.parametrize("target_state", ["stopped", "completed", "failed"])
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_wait(job_api_get_job_by_name_mocker, internal_studio_init_mocker, target_state):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace)

    i = 0

    def get_job_side_effect(*args, **kwargs):
        nonlocal i
        if i < 5:
            i += 1
            return V1Job(id="test-job-id", state="pending", spec=V1JobSpec(cloudspace_id="cloudspace-id"))
        if i < 10:
            i += 1
            return V1Job(id="test-job-id", state="running", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

        return V1Job(id="test-job-id", state=target_state, spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job._job_api.get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job._job_api._client.jobs_service_update_job = update_job_mock

    job.wait(interval=0.1)

    assert get_job_mock.call_count == 11


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_jobv2_wait_timeout(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = Job("test-job", studio.teamspace)

    def get_job_side_effect(*args, **kwargs):
        return V1Job(id="test-job-id", state="running", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job._job_api.get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job._job_api._client.jobs_service_update_job = update_job_mock

    with pytest.raises(TimeoutError):
        job.wait(interval=0.1, timeout=0.1)


@pytest.mark.asyncio()
@pytest.mark.parametrize("target_state", ["stopped", "completed", "failed"])
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
async def test_jobv2_wait_async(job_api_get_job_by_name_mocker, internal_studio_init_mocker, target_state):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace)

    i = 0

    def get_job_side_effect(*args, **kwargs):
        nonlocal i
        if i < 5:
            i += 1
            return V1Job(id="test-job-id", state="pending", spec=V1JobSpec(cloudspace_id="cloudspace-id"))
        if i < 10:
            i += 1
            return V1Job(id="test-job-id", state="running", spec=V1JobSpec(cloudspace_id="cloudspace-id"))
        return V1Job(id="test-job-id", state=target_state, spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job._job_api.get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job._job_api._client.jobs_service_update_job = update_job_mock

    await job.async_wait(interval=0.1)

    assert get_job_mock.call_count == 11


@pytest.mark.asyncio()
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
async def test_jobv2_wait_async_timeout(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace)

    def get_job_side_effect(*args, **kwargs):
        return V1Job(id="test-job-id", state="running", spec=V1JobSpec(cloudspace_id="cloudspace-id"))

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job._job_api.get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job._job_api._client.jobs_service_update_job = update_job_mock

    with pytest.raises(TimeoutError):
        await job.async_wait(interval=0.1, timeout=0.1)


@mock.patch("lightning_sdk.studio._internal_status_to_external_status", return_value=Status.Running)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_submit_job_from_running_studio(
    internal_get_org_api_mocker,
    internal_teamspace_api_mocker,
    internal_studio_init_mocker,
    internal_job_get_cloudspace_mocker,
    job_api_get_job_by_name_mocker,
):
    from lightning_sdk.api.studio_api import StudioApi
    from lightning_sdk.job import Job

    submit_mock = mock.MagicMock()
    Job._submit = submit_mock
    keeping_alive_mock = mock.MagicMock()
    StudioApi.start_keeping_alive = keeping_alive_mock

    with mock.patch.dict(
        os.environ,
        {
            "LIGHTNING_CLOUD_SPACE_ID": "st-abc",
            "LIGHTNING_CLOUD_PROJECT_ID": "ts-abc001",
            "LIGHTNING_INTERACTIVE": "true",
        },
    ):
        Job.run(
            "test-job",
            machine=Machine.CPU,
            command="echo hello",
            teamspace="ts-abc",
            org="org-abc",
        )
    assert keeping_alive_mock.call_count == 0


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_logs_raises_while_running_and_points_to_stream_logs(
    job_api_get_job_by_name_mocker, internal_studio_init_mocker
):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace)

    job._job_api.get_job = mock.MagicMock(return_value=V1Job(id="test-job-id", state="running"))
    # reading logs of a running job is unsupported, and the error should point users at stream_logs
    with pytest.raises(RuntimeError, match="stream_logs"):
        _ = job.logs


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_logs_returns_finished_logs(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace)

    job._job_api.get_job = mock.MagicMock(return_value=V1Job(id="test-job-id", state="completed"))
    logs_mock = mock.MagicMock(return_value="all done")
    job._job_api.get_logs_finished = logs_mock

    assert job.logs == "all done"
    logs_mock.assert_called_once_with(job_id="test-job-id", teamspace_id=job.teamspace.id)


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_job_stream_logs_delegates_to_api(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = Job("test-job", studio.teamspace)

    stream_mock = mock.MagicMock(return_value=iter(["line-1", "line-2"]))
    job._job_api.stream_logs = stream_mock

    result = list(job.stream_logs(follow=True, tail=10, rank=1, idle_timeout=5, timestamps=True))

    assert result == ["line-1", "line-2"]
    stream_mock.assert_called_once_with(
        job_id="test-job-id",
        teamspace_id=job.teamspace.id,
        follow=True,
        tail=10,
        rank=1,
        idle_timeout=5,
        timestamps=True,
    )
