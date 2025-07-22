import importlib
from unittest import mock

import pytest

from lightning_sdk.lightning_cloud.openapi import MultimachinejobsIdBody, V1JobSpec, V1MultiMachineJob
from lightning_sdk.machine import Machine
from lightning_sdk.mmt.v2 import _MMTV2
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace


@pytest.mark.parametrize("machine", [Machine.CPU, Machine.T4_X_4])
@pytest.mark.parametrize("command", [None, "echo hello"])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
@pytest.mark.parametrize(
    ("artifacts_local", "artifacts_remote"), [(None, None), ("", ""), ("/output", "efs:data:some-path")]
)
def test_submit_mmt_v2_image(
    internal_studio_init_mocker, machine, command, env, interruptible, artifacts_local, artifacts_remote
):
    teamspace = Teamspace("ts-abc", org="org-abc")
    job = _MMTV2("test-job", teamspace, _fetch_job=False)

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
        artifacts_local=artifacts_local,
        artifacts_remote=artifacts_remote,
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
        artifacts_local=artifacts_local,
        artifacts_remote=artifacts_remote,
        entrypoint="sh -c",
        path_mappings=None,
        max_runtime=None,
    )


@pytest.mark.parametrize("machine", [Machine.A10G, Machine.DATA_PREP_MAX])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
def test_submit_mmt_v2_studio(internal_studio_init_mocker, machine, env, interruptible):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _MMTV2("test-job", studio.teamspace, _fetch_job=False)
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
        artifacts_local=None,
        artifacts_remote=None,
        entrypoint="sh -c",
        path_mappings=None,
        max_runtime=None,
    )


def test_mmt_run_arg_validation(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    with pytest.raises(
        ValueError,
        match="Studio teamspace does not match provided teamspace."
        " Can only run jobs with Studio envs in the teamspace of that Studio.",
    ):
        _MMTV2.run("some name", Machine.CPU, 5, command="some command", studio=studio, teamspace="other teamspace")

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        _MMTV2.run("", Machine.CPU, 5)

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        _MMTV2.run(None, Machine.CPU, 5)


def test_submit_mmtv2_error_cases(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _MMTV2("test-job", studio.teamspace, _fetch_job=False)

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
    job = _MMTV2("test-job", studio.teamspace, _fetch_job=False)

    job._job_api.get_job_by_name = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer
    # and that class values and function params are mixed correctly
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")


def test_get_mmt_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = _MMTV2("test-job", studio.teamspace, _fetch_job=False)

    # simulate updating internal job
    job._job = V1MultiMachineJob(id="test-job-id")

    job._job_api.get_job = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer
    # and that class values and function params are mixed correctly
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


def test_get_mmt_by_name_first_and_then_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = _MMTV2("test-job", studio.teamspace, _fetch_job=False)
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
    job = _MMTV2("test-job", studio.teamspace)

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

    job = _MMTV2("test-job", studio.teamspace)

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
        ("unknown", "", Machine("unknown", "unknown")),
        ("", "unknown", Machine("unknown", "unknown")),
    ],
)
def test_mmtv2_machine(internal_studio_init_mocker, internal_instance_name, internal_instance_type, expected_machine):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _MMTV2("test-job", studio.teamspace, _fetch_job=False)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1MultiMachineJob(
        id="test-job-id", spec=V1JobSpec(instance_name=internal_instance_name, instance_type=internal_instance_type)
    )
    job._job_api.get_job_by_name = get_job_mock

    assert job.machine == expected_machine
    get_job_mock.assert_called_once()


def test_mmtv2_stop(mmt_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _MMTV2("test-job", studio.teamspace)

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
        body=MultimachinejobsIdBody(desired_state="MultiMachineJob_STATE_STOP"),
    )


def test_mmtv2_delete(mmt_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _MMTV2(
        "test-job",
        studio.teamspace,
    )

    delete_job_mock = mock.MagicMock()
    job._job_api.delete_job = delete_job_mock

    job.delete()

    delete_job_mock.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


def test_mmt_instantiation_fallback_v2_to_v1(internal_studio_init_mocker, internal_mmt_fallback_mocker):
    import lightning_sdk
    from lightning_sdk.mmt.v1 import _MMTV1
    from lightning_sdk.mmt.v2 import _MMTV2

    importlib.reload(lightning_sdk.mmt.mmt)
    from lightning_sdk.mmt.mmt import MMT

    # the internal_mmt_fallback_mocker makes sure that attempts to init a _MMTV2
    # fail with APIExceptions which should trigger a fallback to _MMTV1
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    m = MMT(name="abc", teamspace=studio.teamspace)
    assert isinstance(m._internal_mmt, _MMTV1)

    # when we're not fetching then job (e.g. on job creation) there's no fallback necessary
    m = MMT(name="abc", teamspace=studio.teamspace, _fetch_job=False)
    assert isinstance(m._internal_mmt, _MMTV2)
