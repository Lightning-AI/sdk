from datetime import datetime

import pytest

from lightning_sdk.machine import Machine
from lightning_sdk.plugin import (
    InferenceServerPlugin,
    JobsPlugin,
    MultiMachineDataPrepPlugin,
    MultiMachineTrainingPlugin,
    Plugin,
    SlurmJobsPlugin,
    _run_name,
)
from lightning_sdk.studio import Studio


def test_run_plugin(internal_studio_init_mocker, internal_studio_status_mocker, internal_studio_plugin_run_mocker):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)

    plugin.run()


def test_run_job_plugins(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_get_cloudspace_mocker,
    internal_job_run_mocker,
    internal_job_api_mocker_all_jobs_valid,
):
    studio_1 = Studio("st-ghi", "ts-abc", "org-abc")
    plugin_1 = JobsPlugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio_1)
    plugin_1.run("python my-file.py", name="my-fancy-job-name")

    plugin_2 = JobsPlugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio_1)
    plugin_2.run("python my-file.py", name="my-fancy-job-name")

    studio_2 = Studio("st-ghi-2", "ts-abc", "org-abc")
    plugin_3 = JobsPlugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio_2)
    plugin_3.run("python my-file.py", name="my-fancy-job-name")

    from lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api import CloudSpaceServiceApi

    CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance  # noqa: B018
    from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__

    calls = CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance.mock_calls
    assert len(calls) == 3
    assert calls[0].kwargs["body"].unique_id == __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__["st-ghi"]
    assert calls[1].kwargs["body"].unique_id == __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__["st-ghi"]
    assert calls[2].kwargs["body"].unique_id == __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__["st-ghi-2"]


@pytest.mark.parametrize("cloud_compute", list(Machine))
def test_run_job(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_get_cloudspace_mocker,
    internal_job_run_mocker,
    internal_job_api_mocker_all_jobs_valid,
    cloud_compute,
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = JobsPlugin(
        "jobs", "Launch asynchronous scripts from a Studio - Like submitting a job to a cluster", studio
    )

    with pytest.deprecated_call():
        plugin.run(command="python my-file.py", name="my-fancy-job-name", cloud_compute=cloud_compute)

    plugin.run(command="python my-file.py", name="my-fancy-job-name", machine=cloud_compute)

    # name implicit None
    job = plugin.run(command="python my-file.py", machine=cloud_compute)
    assert job.name != ""

    # set name explicitly to empty string
    job = plugin.run(command="python my-file.py", name="", machine=cloud_compute)
    assert job.name != ""


@pytest.mark.parametrize("cloud_compute", list(Machine))
def test_run_mmt(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_get_cloudspace_mocker,
    internal_mmt_run_mocker,
    internal_job_api_mocker_all_jobs_valid,
    cloud_compute,
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = MultiMachineTrainingPlugin(
        "multi-machine-training", "Train a model across multiple cloud machines", studio
    )

    with pytest.deprecated_call():
        plugin.run(command="python my-file.py", name="my-fancy-mmt-name", num_instances=42, cloud_compute=cloud_compute)

    plugin.run(command="python my-file.py", name="my-fancy-mmt-name", num_instances=42, machine=cloud_compute)


@pytest.mark.parametrize("cloud_compute", list(Machine))
def test_run_inference(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_inference_run_mocker,
    internal_job_api_mocker_all_jobs_valid,
    cloud_compute,
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = InferenceServerPlugin("inference-server", "Deploy an ML model accessible via API", studio)

    with pytest.deprecated_call():
        plugin.run(
            command="python my-file.py",
            name="my-fancy-inference-name",
            min_replicas=1,
            max_replicas=5,
            max_batch_size=10,
            timeout_batching=0.3,
            scale_in_interval=11,
            scale_out_interval=12,
            endpoint="/fancy-predict",
            cloud_compute=cloud_compute,
        )

    plugin.run(
        command="python my-file.py",
        name="my-fancy-inference-name",
        min_replicas=1,
        max_replicas=5,
        max_batch_size=10,
        timeout_batching=0.3,
        scale_in_interval=11,
        scale_out_interval=12,
        endpoint="/fancy-predict",
        machine=cloud_compute,
    )


def test_run_name():
    start_time = datetime.now().replace(second=0, microsecond=0)
    name = _run_name("fancy-abc")
    # removeprefix is python3.10 only, so use replace here
    time_stamp_str = name.replace("fancy-abc-", "")

    time_stamp = datetime.strptime(time_stamp_str, "%b-%d-%H_%M").replace(year=datetime.now().year)

    # assert this has the same time as current time and runs fast!
    assert start_time == time_stamp == datetime.now().replace(second=0, microsecond=0)


@pytest.mark.parametrize("cloud_compute", list(Machine))
def test_run_data_prep(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_data_prep_run_mocker,
    internal_job_api_mocker_all_jobs_valid,
    cloud_compute,
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = MultiMachineDataPrepPlugin(
        "multi-machine-training", "Train a model across multiple cloud machines", studio
    )

    with pytest.deprecated_call():
        plugin.run(
            command="python my-file.py", name="my-fancy-data-prep-name", num_instances=42, cloud_compute=cloud_compute
        )

    plugin.run(command="python my-file.py", name="my-fancy-data-prep-name", num_instances=42, machine=cloud_compute)


def test_slurm_job(internal_studio_init_mocker, internal_studio_status_mocker, internal_slurm_run_mocker):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = SlurmJobsPlugin("slurm", "", studio)
    plugin.run(command="python my-file.py", name="my-fancy-slurm-name", cache_id="2", num_gpus=2)

    with pytest.raises(ValueError, match="The argument `num_gpus` needs to be strictly positive."):
        plugin.run("", num_gpus=0)

    with pytest.raises(ValueError, match="The argument `work_dir` needs to be a proper path on the SLURM Cluster."):
        plugin.run("", work_dir="")
