from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import JobsServiceUpdateMultiMachineJobBody, V1JobSpec, V1MultiMachineJob
from lightning_sdk.machine import Machine
from lightning_sdk.mmt import MMT
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace


@pytest.mark.parametrize("machine", [Machine.CPU, Machine.T4_X_4])
@pytest.mark.parametrize("command", [None, "echo hello"])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
def test_submit_mmt_v2_image(internal_studio_init_mocker, machine, command, env, interruptible):
    teamspace = Teamspace("ts-abc", org="org-abc")
    job = MMT("test-job", teamspace, _fetch_job=False)

    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock
    job._submit(
        num_machines=5,
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
        num_machines=5,
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
    )


@pytest.mark.parametrize("machine", [Machine.L4, Machine.DATA_PREP_MAX])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
def test_submit_mmt_v2_studio(internal_studio_init_mocker, machine, env, interruptible):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = MMT("test-job", studio.teamspace, _fetch_job=False)
    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock
    job._submit(
        machine=machine,
        num_machines=5,
        cloud_account=studio.cloud_account,
        studio=studio,
        env=env,
        interruptible=interruptible,
        command="echo hello",
    )

    submit_mock.assert_called_once_with(
        name="test-job",
        num_machines=5,
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
    )


def test_mmt_run_arg_validation(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    with pytest.raises(
        ValueError,
        match="Studio teamspace does not match provided teamspace."
        " Can only run jobs with Studio envs in the teamspace of that Studio.",
    ):
        MMT.run("some name", 5, Machine.CPU, command="some command", studio=studio, teamspace="other teamspace")

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        MMT.run("", 5, Machine.CPU)

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        MMT.run(None, 5, Machine.CPU)


def test_mmt_run_entrypoint_validation(internal_studio_init_mocker):
    """Test entrypoint validation logic for MMT image jobs."""
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    # Test that empty string entrypoint is converted to None (use container default)
    submit_mock = mock.MagicMock()
    with mock.patch.object(MMT, "_submit", submit_mock):
        MMT.run(
            "test-job",
            num_machines=2,
            machine=Machine.CPU,
            command="echo hello",
            image="alpine:latest",
            teamspace=studio.teamspace,
            entrypoint="",
        )
        submit_mock.assert_called_once()
        assert submit_mock.call_args.kwargs["entrypoint"] is None

    # Test that when command is provided with default entrypoint, sh -c is used
    submit_mock.reset_mock()
    with mock.patch.object(MMT, "_submit", submit_mock):
        MMT.run(
            "test-job",
            num_machines=2,
            machine=Machine.CPU,
            command="echo hello",
            image="alpine:latest",
            teamspace=studio.teamspace,
        )
        submit_mock.assert_called_once()
        assert submit_mock.call_args.kwargs["entrypoint"] == "sh -c"

    # Test that no command with empty entrypoint uses container defaults
    submit_mock.reset_mock()
    with mock.patch.object(MMT, "_submit", submit_mock):
        MMT.run(
            "test-job",
            num_machines=2,
            machine=Machine.CPU,
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
        MMT.run(
            "test-job",
            num_machines=2,
            machine=Machine.CPU,
            command="echo hello",
            studio=studio,
            entrypoint="/bin/bash -c",
        )


def test_submit_mmtv2_error_cases(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = MMT("test-job", studio.teamspace, _fetch_job=False)

    with pytest.raises(
        ValueError, match="image and studio are mutually exclusive as both define the environment to run the job in"
    ):
        job._submit(
            machine=Machine.T4_X_4,
            num_machines=5,
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
            num_machines=5,
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
            num_machines=5,
            studio=None,
            image=None,
            command="echo hello",
            env={"key": "value"},
            interruptible=False,
            cloud_account=studio.cloud_account,
        )


def test_get_mmt_by_name(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = MMT("test-job", studio.teamspace, _fetch_job=False)

    job._job_api.get_job_by_name = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer
    # and that class values and function params are mixed correctly
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")


def test_get_mmt_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = MMT("test-job", studio.teamspace, _fetch_job=False)

    # simulate updating internal job
    job._job = V1MultiMachineJob(id="test-job-id")

    job._job_api.get_job = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer
    # and that class values and function params are mixed correctly
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


def test_get_mmt_by_name_first_and_then_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = MMT("test-job", studio.teamspace, _fetch_job=False)
    job._job_api.get_job_by_name = mock.MagicMock()

    job._job_api.get_job = mock.MagicMock()

    job._update_internal_job()
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")

    # simulate updating internal job
    job._job = V1MultiMachineJob(id="test-job-id")

    job._update_internal_job()
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


def test_get_mmt_by_name_on_init(mmt_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = MMT("test-job", studio.teamspace)

    assert hasattr(job, "_job")
    assert job._job is not None

    assert job._job.id == "test-job-id"


@pytest.mark.parametrize(
    ("internal_status", "external_status"),
    [
        ("MultiMachineJob_STATE_UNSPECIFIED", Status.Pending),
        ("MultiMachineJob_STATE_RUNNING", Status.Running),
        ("MultiMachineJob_STATE_STOPPED", Status.Stopped),
        ("MultiMachineJob_STATE_STOP", Status.Stopping),
        ("MultiMachineJob_STATE_FAILED", Status.Failed),
        ("MultiMachineJob_STATE_COMPLETED", Status.Completed),
    ],
)
def test_mmtv2_status(mmt_api_get_job_by_name_mocker, internal_studio_init_mocker, internal_status, external_status):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = MMT("test-job", studio.teamspace)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1MultiMachineJob(id="test-job-id", state=internal_status)
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
def test_mmtv2_machine(
    internal_studio_init_mocker,
    internal_studio_api_mocker_get_machine,
    internal_instance_name,
    internal_instance_type,
    expected_machine,
):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = MMT("test-job", studio.teamspace, _fetch_job=False)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1MultiMachineJob(
        id="test-job-id",
        spec=V1JobSpec(
            instance_name=internal_instance_name, instance_type=internal_instance_type, cluster_id="cluster_abc"
        ),
    )
    job._job_api.get_job_by_name = get_job_mock

    assert job.machine == expected_machine
    get_job_mock.assert_called_once()


def test_mmtv2_stop(mmt_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = MMT("test-job", studio.teamspace)

    i = 0

    def get_job_side_effect(*args, **kwargs):
        nonlocal i
        if i < 5:
            i += 1
            return V1MultiMachineJob(
                id="test-job-id",
                state="MultiMachineJob_STATE_RUNNING",
                spec=V1JobSpec(cloudspace_id="cloudspace-id"),
            )

        return V1MultiMachineJob(
            id="test-job-id",
            state="MultiMachineJob_STATE_STOPPED",
            spec=V1JobSpec(cloudspace_id="cloudspace-id"),
        )

    get_job_mock = mock.MagicMock()
    get_job_mock.side_effect = get_job_side_effect
    job._job_api.get_job = get_job_mock

    update_job_mock = mock.MagicMock()
    job._job_api._client.jobs_service_update_multi_machine_job = update_job_mock

    job.stop()

    assert get_job_mock.call_count == 6
    update_job_mock.assert_called_once_with(
        id="test-job-id",
        project_id="ts-abc001",
        body=JobsServiceUpdateMultiMachineJobBody(desired_state="MultiMachineJob_STATE_STOP"),
    )


def test_mmtv2_delete(mmt_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = MMT(
        "test-job",
        studio.teamspace,
    )

    delete_job_mock = mock.MagicMock()
    job._job_api.delete_job = delete_job_mock

    job.delete()

    delete_job_mock.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")
