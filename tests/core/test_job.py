from lightning_sdk.studio import Studio
from lightning_sdk.job import Job
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.job.work import Work
from lightning_sdk.status import Status
from lightning_sdk.lightning_cloud.openapi import Externalv1LightningappInstance
from unittest import mock
import os
import pytest
from lightning_sdk.machine import Machine


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
