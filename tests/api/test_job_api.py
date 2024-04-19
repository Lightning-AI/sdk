from lightning_sdk.api.job_api import JobApi
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
    V1LightningappInstanceState,
)

import pytest


def test_get_job(internal_job_api_mocker_get_job):
    job_api = JobApi()
    job = job_api.get_job("j-abc", "ts-abc")
    assert isinstance(job, Externalv1LightningappInstance)


def test_get_job_error(internal_job_api_mocker_get_job):
    job_api = JobApi()
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
    job_api = JobApi()
    status = job_api.get_job_status(name, "ts-abc")
    if expected_status is None:
        assert status is None
    else:
        assert isinstance(status, str)
    assert status == expected_status
