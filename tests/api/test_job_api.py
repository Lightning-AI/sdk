from lightning_sdk.api.job_api import JobApi
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1LightningappInstance,
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
