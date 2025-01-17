import importlib
import os
from unittest import mock

import pytest

from lightning_sdk.job import Job
from lightning_sdk.job.v1 import _JobV1
from lightning_sdk.job.v2 import _JobV2
from lightning_sdk.job.work import Work
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    JobsIdBody1,
    V1ComputeConfig,
    V1EnvVar,
    V1Job,
    V1JobSpec,
    V1LightningappInstanceSpec,
    V1LightningappInstanceState,
    V1LightningappInstanceStatus,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.teamspace import Teamspace


@mock.patch.dict(os.environ, clear=True)
def test_job_init(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_api_mocker_get_job,
):
    job = Job("j-abc", "ts-abc", org="org-abc")
    assert isinstance(job._job, Externalv1LightningappInstance)

    assert isinstance(job.teamspace, Teamspace)
    assert job.teamspace.name == "ts-abc"


@mock.patch.dict(os.environ, clear=True)
def test_job_init_error(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_api_mocker_get_job,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")

    with pytest.raises(ValueError, match="Job xyz does not exist in Teamspace ts-abc"):
        Job("xyz", studio.teamspace)


@mock.patch.dict(os.environ, clear=True)
@pytest.mark.parametrize(
    ("name", "expected_status"),
    [
        ("j-abc", Status.Stopped),  # None
        ("j-def", Status.Pending),  # "LIGHTNINGAPP_INSTANCE_STATE_UNSPECIFIED"
        ("j-ghi", Status.Pending),  # "LIGHTNINGAPP_INSTANCE_STATE_IMAGE_BUILDING"
        ("j-jkl", Status.Pending),  # "LIGHTNINGAPP_INSTANCE_STATE_NOT_STARTED"
        ("j-mno", Status.Pending),  # "LIGHTNINGAPP_INSTANCE_STATE_PENDING"
        ("j-pqr", Status.Running),  # "LIGHTNINGAPP_INSTANCE_STATE_RUNNING"
        ("j-stu", Status.Failed),  # "LIGHTNINGAPP_INSTANCE_STATE_FAILED"
        ("j-vwx", Status.Stopped),  # "LIGHTNINGAPP_INSTANCE_STATE_STOPPED"
        ("j-yz", Status.Completed),  # "LIGHTNINGAPP_INSTANCE_STATE_COMPLETED"
    ],
)
def test_job_status(
    internal_job_api_mocker_get_job_status,
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    name,
    expected_status,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")
    job = Job(name, studio.teamspace)
    status = job.status
    assert isinstance(status, Status)

    assert status == expected_status


@mock.patch.dict(os.environ, clear=True)
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
def test_delete_job(
    internal_job_api_mocker_delete_job,
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


@mock.patch.dict(os.environ, clear=True)
def test_get_work(
    internal_job_api_mocker_get_work,
    internal_studio_init_mocker,
    internal_studio_status_mocker,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")
    job = Job("j-abc", studio.teamspace)
    assert isinstance(job.work, Work)

    assert job.work.id == "w-abc"
    assert job.work.name == "w-abc"

    assert job.work.machine == Machine.T4_X_4
    assert job.machine == Machine.T4_X_4


def test_select_job_backend_correctly_v1(job_backend_selector_mocker_v1):
    from lightning_sdk.job.base import _BaseJob
    from lightning_sdk.job.job import _has_jobs_v2
    from lightning_sdk.job.v1 import _JobV1
    from lightning_sdk.job.v2 import _JobV2

    assert _has_jobs_v2() is False
    j = Job("test-job", "ts-abc", org="org-abc", _fetch_job=False)

    assert isinstance(j, _BaseJob)
    assert issubclass(Job, _BaseJob)
    assert isinstance(j._internal_job, _JobV1)
    assert not isinstance(j._internal_job, _JobV2)


def test_select_job_backend_correctly_v2(job_backend_selector_mocker_v2):
    import lightning_sdk
    from lightning_sdk.job.base import _BaseJob
    from lightning_sdk.job.job import _has_jobs_v2
    from lightning_sdk.job.v1 import _JobV1
    from lightning_sdk.job.v2 import _JobV2

    importlib.reload(lightning_sdk.job.job)
    from lightning_sdk.job.job import Job

    assert _has_jobs_v2() is True
    j = Job("test-job", "ts-abc", org="org-abc", _fetch_job=False)

    assert isinstance(j, _BaseJob)
    assert issubclass(Job, _BaseJob)
    assert isinstance(j._internal_job, _JobV2)
    assert not isinstance(j._internal_job, _JobV1)


@pytest.mark.parametrize("machine", [Machine.CPU, Machine.T4_X_4])
@pytest.mark.parametrize("command", [None, "echo hello"])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
@pytest.mark.parametrize(
    ("artifacts_local", "artifacts_remote"), [(None, None), ("", ""), ("/output", "efs:data:some-path")]
)
def test_submit_job_v2_image(
    internal_studio_init_mocker, machine, command, env, interruptible, artifacts_local, artifacts_remote
):
    teamspace = Teamspace("ts-abc", org="org-abc")
    job = _JobV2("test-job", teamspace, _fetch_job=False)

    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock

    job._submit(
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
    )


@pytest.mark.parametrize("machine", [Machine.A10G, Machine.DATA_PREP_MAX])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
def test_submit_job_v2_studio(internal_studio_init_mocker, machine, env, interruptible):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)
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
        artifacts_local=None,
        artifacts_remote=None,
        entrypoint="sh -c",
    )


def test_jobv2_run_arg_validation(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    with pytest.raises(
        ValueError,
        match="Studio teamspace does not match provided teamspace."
        " Can only run jobs with Studio envs in the teamspace of that Studio.",
    ):
        _JobV2.run("some name", Machine.CPU, command="some command", studio=studio, teamspace="other teamspace")

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        _JobV2.run("", Machine.CPU)

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        _JobV2.run(None, Machine.CPU)


def test_submit_jobv2_error_cases(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

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


def test_get_job_by_name(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    job._job_api.get_job_by_name = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer
    # and that class values and function params are mixed correctly
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")


def test_get_job_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    # simulate updating internal job
    job._job = V1Job(id="test-job-id")

    job._job_api.get_job = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer and that class values
    # and function params are mixed correctly
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


def test_get_job_by_name_first_and_then_by_id(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)
    job._job_api.get_job_by_name = mock.MagicMock()

    job._job_api.get_job = mock.MagicMock()

    job._update_internal_job()
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")

    # simulate updating internal job
    job._job = V1Job(id="test-job-id")

    job._update_internal_job()
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")


def test_get_job_by_name_on_init(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace)

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
def test_jobv2_status(job_api_get_job_by_name_mocker, internal_studio_init_mocker, internal_status, external_status):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace)

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
        ("unknown", None, "unknown"),
        ("", "unknown", "unknown"),
    ],
)
def test_jobv2_machine(internal_studio_init_mocker, internal_instance_name, internal_instance_type, expected_machine):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1Job(
        id="test-job-id", spec=V1JobSpec(instance_name=internal_instance_name, instance_type=internal_instance_type)
    )
    job._job_api.get_job_by_name = get_job_mock

    assert job.machine == expected_machine
    get_job_mock.assert_called_once()


def test_jobv2_stop(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace)

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
        id="test-job-id", project_id="ts-abc001", body=JobsIdBody1(cloudspace_id="cloudspace-id", state="stopped")
    )


def test_jobv2_delete(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2(
        "test-job",
        studio.teamspace,
    )

    delete_job_mock = mock.MagicMock()
    job._job_api.delete_job = delete_job_mock

    job.delete()

    delete_job_mock.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001", cloudspace_id="st-abc")


def test_submit_jobv2_studio_resolve(
    job_backend_selector_mocker_v2,
    internal_studio_init_mocker,
    internal_job_get_cloudspace_mocker,
    job_api_get_job_by_name_mocker,
):
    import lightning_sdk
    from lightning_sdk.job.v2 import _JobV2

    importlib.reload(lightning_sdk.job.job)
    from lightning_sdk.job.job import Job

    submit_mock = mock.MagicMock()
    _JobV2._submit = submit_mock

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
        image_credentials=None,
        artifacts_local=None,
        artifacts_remote=None,
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
def test_submit_jobv2_studio_path(
    job_backend_selector_mocker_v2,
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
    import lightning_sdk
    from lightning_sdk.job.v2 import _JobV2

    importlib.reload(lightning_sdk.job.job)
    from lightning_sdk.job.job import Job

    submit_mock = mock.MagicMock()
    _JobV2._submit = submit_mock

    job = Job.run(
        "test-job",
        machine=Machine.CPU,
        command="echo hello",
        studio=studio,
        image=image,
        teamspace="ts-abc",
        org="org-abc",
        artifacts_local=artifacts_source,
        artifacts_remote=artifacts_destination,
    )

    submit_mock.assert_called_once_with(
        command="echo hello",
        cloud_account=None if image else "c-abc",
        env=None,
        image=image,
        interruptible=False,
        machine=Machine.CPU,
        studio=None if image else Studio(name="st-abc", teamspace="ts-abc", org="org-abc"),
        cloud_account_auth=False,
        image_credentials=None,
        artifacts_local=artifacts_source,
        artifacts_remote=artifacts_destination,
    )

    job._internal_job._job = V1Job(
        name="test-job",
        spec=V1JobSpec(
            image=image or "", artifacts_source=artifacts_source, artifacts_destination=artifacts_destination
        ),
    )

    assert job.artifact_path == expected_artifacts_path
    assert job.snapshot_path == expected_snapshot_path


def test_job_logs_v2(
    internal_job_logs_mocker,
    job_api_get_job_by_name_mocker,
    internal_studio_init_mocker,
    job_api_get_job_by_id_mocker,
):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2(
        "test-job",
        studio.teamspace,
    )

    assert job.logs == "⚡  ~ echo Hello\nHello\n"


def test_job_logs_v1(
    internal_job_logs_mocker,
    internal_studio_init_mocker,
    internal_job_api_mocker_get_work,
):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV1(
        "j-abc",
        studio.teamspace,
    )

    assert job.logs == "⚡  ~ echo Hello\nHello\n"


def test_job_v2_dict_json(internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    internal_job = V1Job(
        name="my-job",
        project_id="ts-abc",
        spec=V1JobSpec(cloudspace_id="st-abc", command="some command", instance_type="cpu-4"),
        state="running",
    )

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = internal_job
    get_studio_name_mock = mock.MagicMock()
    get_studio_name_mock.return_value = studio.name
    job = _JobV2("my-job", teamspace=studio.teamspace, _fetch_job=False)
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

    assert job.json() == (
        '{\n    "command": "some command",\n    "image": null,\n    "machine": "CPU",\n    '
        '"name": "my-job",\n    "status": "Running",\n    "studio": "st-abc",\n    "teamspace": "org-abc/ts-abc"\n}'
    )


def test_job_v1_dict_json(internal_studio_init_mocker, internal_job_api_mocker_get_work):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    internal_job = Externalv1LightningappInstance(
        name="my-job",
        project_id="ts-abc",
        spec=V1LightningappInstanceSpec(
            cloud_space_id="st-abc",
            compute_config=V1ComputeConfig(instance_type="cpu-4"),
            env=[
                V1EnvVar(name="foo", value="bar"),
                V1EnvVar(name="bar", value="foo"),
                V1EnvVar(name="COMMAND", value="some command"),
            ],
        ),
        status=V1LightningappInstanceStatus(phase=V1LightningappInstanceState.RUNNING),
    )

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = internal_job
    get_studio_name_mock = mock.MagicMock()
    get_studio_name_mock.return_value = studio.name
    get_status_mock = mock.MagicMock()
    get_status_mock.return_value = internal_job.status.phase

    job = _JobV1("my-job", teamspace=studio.teamspace, _fetch_job=False)
    job._job = internal_job
    job._update_internal_job = get_job_mock
    job._job_api.get_studio_name = get_studio_name_mock
    job._job_api.get_job_status = get_status_mock
    job_dict = job.dict()

    assert job_dict["name"] == "my-job"
    assert job_dict["teamspace"] == "org-abc/ts-abc"
    assert job_dict["studio"] == "st-abc"
    assert job_dict["image"] is None
    assert job_dict["command"] == "some command"
    assert job_dict["status"] == Status.Running
    assert job_dict["machine"] == Machine.T4_X_4  # coming from the work

    assert job.json() == (
        '{\n    "command": "some command",\n    "image": null,\n    "machine": "T4_X_4",\n    '
        '"name": "my-job",\n    "status": "Running",\n    "studio": "st-abc",\n    "teamspace": "org-abc/ts-abc"\n}'
    )


def test_job_instantiation_fallback_v2_to_v1(
    internal_studio_init_mocker, job_backend_selector_mocker_v2, internal_job_fallback_mocker
):
    import lightning_sdk
    from lightning_sdk.job.v1 import _JobV1
    from lightning_sdk.job.v2 import _JobV2

    importlib.reload(lightning_sdk.job.job)
    from lightning_sdk.job.job import Job

    # the internal_job_fallback_mocker makes sure that attempts to init a _JobV2
    # fail with APIExceptions which should trigger a fallback to _JobV1
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    j = Job(name="abc", teamspace=studio.teamspace)
    assert isinstance(j._internal_job, _JobV1)

    # when we're not fetching then job (e.g. on job creation) there's no fallback necessary
    j = Job(name="abc", teamspace=studio.teamspace, _fetch_job=False)
    assert isinstance(j._internal_job, _JobV2)
