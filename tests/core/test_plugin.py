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


@pytest.mark.parametrize(
    "cloud_compute", [machine for machine in Machine.__dict__.values() if isinstance(machine, Machine)]
)
def test_run_job(
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_job_get_cloudspace_mocker,
    internal_job_run_mocker,
    internal_job_api_mocker_all_jobs_valid,
    job_api_get_job_by_name_mocker,
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


@pytest.mark.parametrize(
    "cloud_compute", [machine for machine in Machine.__dict__.values() if isinstance(machine, Machine)]
)
def test_run_mmt(
    internal_auth_mocker,
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

    plugin.run(command="python my-file.py", name="my-fancy-mmt-name", num_instances=42, machine=cloud_compute)


@pytest.mark.parametrize(
    "cloud_compute", [machine for machine in Machine.__dict__.values() if isinstance(machine, Machine)]
)
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


@pytest.mark.parametrize(
    "cloud_compute", [machine for machine in Machine.__dict__.values() if isinstance(machine, Machine)]
)
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
