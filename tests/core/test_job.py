import importlib

from lightning_sdk.studio import Studio
from lightning_sdk.job import Job
from lightning_sdk.job.v2 import _JobV2
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.job.work import Work
from lightning_sdk.status import Status
from lightning_sdk.lightning_cloud.openapi import Externalv1LightningappInstance
from unittest import mock
import os
import pytest
from lightning_sdk.machine import Machine
from lightning_sdk.lightning_cloud.openapi import V1GetUserResponse
from lightning_sdk.lightning_cloud.openapi import V1UserFeatures
from lightning_sdk.lightning_cloud.openapi import V1Job, V1JobSpec, JobsIdBody1


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
    "name,expected_status",
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
        job.status

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
    from lightning_sdk.job.job import _has_jobs_v2
    from lightning_sdk.job.v1 import _JobV1
    from lightning_sdk.job.v2 import _JobV2
    from lightning_sdk.api.job_api import JobApiV1
    from lightning_sdk.job.base import _BaseJob

    assert _has_jobs_v2() is False
    j = Job("test-job", "ts-abc", org="org-abc", _fetch_job=False)

    assert isinstance(j, _BaseJob)
    assert issubclass(Job, _BaseJob)
    assert isinstance(j._internal_job, _JobV1)
    assert not isinstance(j._internal_job, _JobV2)


def test_select_job_backend_correctly_v2(job_backend_selector_mocker_v2):
    from lightning_sdk.job.job import _has_jobs_v2
    from lightning_sdk.job.v2 import _JobV2
    from lightning_sdk.job.v1 import _JobV1
    from lightning_sdk.api.job_api import JobApiV2
    from lightning_sdk.job.base import _BaseJob

    import lightning_sdk
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
def test_submit_job_v2_image(internal_studio_init_mocker, machine, command, env, interruptible):

        teamspace = Teamspace("ts-abc", org="org-abc")
        job = _JobV2("test-job", teamspace, _fetch_job=False)

        submit_mock = mock.MagicMock()
        job._job_api.submit_job = submit_mock

        job._submit(machine=machine, image="image-abc", command=command, env=env, interruptible=interruptible, cluster="c-abc")

        # test that everything was passed along correctly to the api layer and that class values and function params are mixed correctly
        submit_mock.assert_called_once_with(name="test-job", command=command, cluster_id="c-abc", teamspace_id="ts-abc001", studio_id=None, image="image-abc", machine=machine, interruptible=interruptible, env=env)


@pytest.mark.parametrize("machine", [Machine.A10G, Machine.DATA_PREP_MAX])
@pytest.mark.parametrize("env", [None, {"key": "value"}])
@pytest.mark.parametrize("interruptible", [True, False])
def test_submit_job_v2_studio(internal_studio_init_mocker, machine, env, interruptible):

    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)
    submit_mock = mock.MagicMock()
    job._job_api.submit_job = submit_mock
    job._submit(machine=machine, cluster=studio.cluster, studio=studio, env=env, interruptible=interruptible, command="echo hello")

    submit_mock.assert_called_once_with(name="test-job", command="echo hello", cluster_id="c-abc", teamspace_id="ts-abc001", studio_id="st-abc", image=None, machine=machine, interruptible=interruptible, env=env)


def test_jobv2_run_arg_validation(internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

    with pytest.raises(ValueError, match="Studio teamspace does not match provided teamspace. Can only run jobs with Studio envs in the teamspace of that Studio."):
        job = _JobV2.run("some name", Machine.CPU, command="some command", studio=studio, teamspace='other teamspace')

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        _JobV2.run("", Machine.CPU)

    with pytest.raises(ValueError, match="A job needs to have a name!"):
        _JobV2.run(None, Machine.CPU)

def test_submit_jobv2_error_cases(internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    with pytest.raises(ValueError, match="image and studio are mutually exclusive as both define the environment to run the job in"):
        job._submit(machine=Machine.T4_X_4, studio=studio, image="image-abc", command="echo hello", env={"key": "value"}, interruptible=False, cluster=studio.cluster)

    with pytest.raises(ValueError, match="command is required when using a studio"):
        job._submit(machine=Machine.T4_X_4, studio=studio, image=None, command=None, env={"key": "value"}, interruptible=False, cluster=studio.cluster)

    with pytest.raises(ValueError, match="either image or studio must be provided"):
        job._submit(machine=Machine.T4_X_4, studio=None, image=None, command="echo hello", env={"key": "value"}, interruptible=False, cluster=studio.cluster)

def test_get_job_by_name(internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    job._job_api.get_job_by_name = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer and that class values and function params are mixed correctly
    job._job_api.get_job_by_name.assert_called_once_with(name="test-job", teamspace_id="ts-abc001")

def test_get_job_by_id(internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    # simulate updating internal job
    job._job = V1Job(id="test-job-id")

    job._job_api.get_job = mock.MagicMock()
    job._update_internal_job()

    # test that everything was passed along correctly to the api layer and that class values and function params are mixed correctly
    job._job_api.get_job.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001")

def test_get_job_by_name_first_and_then_by_id(internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")
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
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")
    job = _JobV2("test-job", studio.teamspace)

    assert hasattr(job, "_job")
    assert job._job is not None

    assert job._job.id == "test-job-id"


@pytest.mark.parametrize("internal_status, external_status", [
    ("pending", Status.Pending),
    ("running", Status.Running),
    ("completed", Status.Completed),
    ("failed", Status.Failed),
    ("stopped", Status.Stopped),
])
def test_jobv2_status(job_api_get_job_by_name_mocker, internal_studio_init_mocker, internal_status, external_status):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1Job(id="test-job-id", state=internal_status)
    job._job_api.get_job = get_job_mock

    assert job.status == external_status
    get_job_mock.assert_called_once()


@pytest.mark.parametrize(
    "internal_instance_name, internal_instance_type, expected_machine",
    [
        ("g4dn.12xlarge", None, Machine.T4_X_4),
        ("p4d.24xlarge", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", "p4d.24xlarge", Machine.A100_X_8),
        ("unknown", None, "unknown"),
        ("", "unknown", "unknown"),
    ],
)
def test_jobv2_machine(internal_studio_init_mocker, internal_instance_name, internal_instance_type, expected_machine):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace, _fetch_job=False)

    get_job_mock = mock.MagicMock()
    get_job_mock.return_value = V1Job(id="test-job-id", spec=V1JobSpec(instance_name=internal_instance_name, instance_type=internal_instance_type))
    job._job_api.get_job_by_name = get_job_mock

    assert job.machine == expected_machine
    get_job_mock.assert_called_once()


def test_jobv2_stop(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

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
    update_job_mock.assert_called_once_with(id="test-job-id", project_id="ts-abc001", body=JobsIdBody1(cloudspace_id="cloudspace-id", state="stopped"))


def test_jobv2_delete(job_api_get_job_by_name_mocker, internal_studio_init_mocker):
    studio = Studio(name=f"st-abc", teamspace="ts-abc", org="org-abc")

    job = _JobV2("test-job", studio.teamspace,)

    delete_job_mock = mock.MagicMock()
    job._job_api.delete_job = delete_job_mock

    job.delete()

    delete_job_mock.assert_called_once_with(job_id="test-job-id", teamspace_id="ts-abc001", cloudspace_id=None)


def test_submit_jobv2_studio_resolve(job_backend_selector_mocker_v2, internal_studio_init_mocker):
    from lightning_sdk.job.v2 import _JobV2
    import lightning_sdk
    importlib.reload(lightning_sdk.job.job)
    from lightning_sdk.job.job import Job

    submit_mock = mock.MagicMock()
    _JobV2._submit = submit_mock

    job = Job.run("test-job", machine=Machine.CPU, command="echo hello", studio="st-abc", teamspace="ts-abc", org="org-abc")

    submit_mock.assert_called_once_with(command="echo hello", cluster="c-abc", env=None, image=None, interruptible=False, machine=Machine.CPU, studio=Studio(name="st-abc", teamspace="ts-abc", org="org-abc"))
