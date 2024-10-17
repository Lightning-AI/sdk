from lightning_sdk.api.job_api import JobApiV1
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    Externalv1Lightningwork,
)
from click.exceptions import ClickException
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
import pytest
from unittest import mock
from lightning_sdk.job.v2 import JobApiV2

from lightning_sdk.machine import Machine


def test_get_job(internal_job_api_mocker_get_job):
    job_api = JobApiV1()
    job = job_api.get_job("j-abc", "ts-abc")
    assert isinstance(job, Externalv1LightningappInstance)


def test_get_job_error(internal_job_api_mocker_get_job):
    job_api = JobApiV1()
    with pytest.raises(ValueError, match="Job xyz does not exist"):
        job_api.get_job("xyz", "ts-abc")


@pytest.mark.parametrize(
    "name,expected_status",
    [
        ("j-abc", None),
        ("j-def", "LIGHTNINGAPP_INSTANCE_STATE_UNSPECIFIED"),
        ("j-ghi", "LIGHTNINGAPP_INSTANCE_STATE_IMAGE_BUILDING"),
        ("j-jkl", "LIGHTNINGAPP_INSTANCE_STATE_NOT_STARTED"),
        ("j-mno", "LIGHTNINGAPP_INSTANCE_STATE_PENDING"),
        ("j-pqr", "LIGHTNINGAPP_INSTANCE_STATE_RUNNING"),
        ("j-stu", "LIGHTNINGAPP_INSTANCE_STATE_FAILED"),
        ("j-vwx", "LIGHTNINGAPP_INSTANCE_STATE_STOPPED"),
        ("j-yz", "LIGHTNINGAPP_INSTANCE_STATE_COMPLETED"),
    ],
)
def test_job_status(internal_job_api_mocker_get_job_status, name, expected_status):
    job_api = JobApiV1()
    status = job_api.get_job_status(name, "ts-abc")
    if expected_status is None:
        assert status is None
    else:
        assert isinstance(status, str)
    assert status == expected_status


def test_stop_job(internal_job_api_mocker_stop_job):
    job_api = JobApiV1()
    status = job_api.get_job_status("j-abc", "ts-abc")

    assert status == "LIGHTNINGAPP_INSTANCE_STATE_RUNNING"
    job_api.stop_job("j-abc", "ts-abc")
    status = job_api.get_job_status("j-abc", "ts-abc")
    assert status == "LIGHTNINGAPP_INSTANCE_STATE_STOPPED"


def test_delete_job(internal_job_api_mocker_delete_job):
    job_api = JobApiV1()
    job_api.delete_job("j-abc", "ts-abc")

    with pytest.raises((ApiException, ClickException)):
        job_api.get_job_status("j-abc", "ts-abc")

    with pytest.raises(ValueError, match="Job j-abc does not exist"):
        job_api.get_job("j-abc", "ts-abc")


def test_get_work(internal_job_api_mocker_get_work):
    job_api = JobApiV1()
    works = job_api.list_works("j-abc", "ts-abc")
    assert isinstance(works, list)
    for w in works:
        assert isinstance(w, Externalv1Lightningwork)
        assert w.id == "w-abc"
        assert w.display_name == "work abc"
        assert w.name == "root.w-abc"

    w = job_api.get_work("j-abc", "ts-abc", "w-abc")
    assert isinstance(w, Externalv1Lightningwork)
    assert w.id == "w-abc"
    assert w.name == "root.w-abc"
    assert w.display_name == "work abc"

def test_job_v2_submit_job(internal_studio_init_mocker):
    from lightning_sdk.lightning_cloud.openapi import V1JobSpec, ProjectIdJobsBody, V1EnvVar
    job_api = JobApiV2()

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock


    job_api.submit_job(name="test-job", cluster_id="c-abc", teamspace_id="ts-abc", image="", studio_id="st-abc", machine=Machine.T4_X_4, interruptible=False, env={"key": "value"}, command="echo hello")

    spec = V1JobSpec(
            cloudspace_id="st-abc",
            cluster_id="c-abc",
            command="echo hello",
            env=[V1EnvVar(name="key", value="value")],
            image="",
            instance_name="g4dn.12xlarge",
            run_id=mock.ANY,
            spot=False,
        )
    body = ProjectIdJobsBody(name="test-job", spec=spec)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)

    create_job_mock = mock.MagicMock()
    job_api._client.jobs_service_create_job = create_job_mock
    job_api.submit_job(name="test-job", cluster_id="c-abc", teamspace_id="ts-abc", studio_id="", image="image-abc", machine=Machine.T4_X_4, interruptible=True, env=None, command=None)

    spec = V1JobSpec(
            cloudspace_id="",
            cluster_id="c-abc",
            command="",
            env=[],
            image="image-abc",
            instance_name="g4dn.12xlarge",
            run_id=mock.ANY,
            spot=True,
        )
    body = ProjectIdJobsBody(name="test-job", spec=spec)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)
    create_job_mock.assert_called_once_with(project_id="ts-abc", body=body)
