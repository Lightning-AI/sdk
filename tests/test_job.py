from lightning_sdk.studio import Studio
from lightning_sdk.job import Job

from lightning_sdk.lightning_cloud.openapi import Externalv1LightningappInstance
from unittest import mock
import os
import pytest


@mock.patch.dict(os.environ, clear=True)
def test_job_init(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_api_mocker_get_job,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")
    job = Job("j-abc", studio)
    assert isinstance(job._job, Externalv1LightningappInstance)


@mock.patch.dict(os.environ, clear=True)
def test_job_init_error(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_api_mocker_get_job,
):
    studio = Studio("st-abc", "ts-abc", org="org-abc")

    with pytest.raises(ValueError, match="Job xyz does not exist in Teamspace ts-abc"):
        Job("xyz", studio)
