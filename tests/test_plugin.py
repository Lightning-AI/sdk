import pytest

from lightning_sdk.machine import Machine
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.plugin import Plugin, JobsPlugin, MultiMachineTrainingPlugin, InferenceServerPlugin, _run_name
from datetime import datetime
import time


def test_run_plugin(internal_studio_init_mocker, internal_studio_status_mocker, internal_studio_plugin_run_mocker):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)

    plugin.run()


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_job(internal_studio_init_mocker, internal_studio_status_mocker, internal_job_run_mocker, cloud_compute):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = JobsPlugin(
        "jobs", "Launch asynchronous scripts from a Studio - Like submitting a job to a cluster", studio
    )

    plugin.run(command="python my-file.py", name="my-fancy-job-name", cloud_compute=cloud_compute)


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_mmt(internal_studio_init_mocker, internal_studio_status_mocker, internal_mmt_run_mocker, cloud_compute):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = MultiMachineTrainingPlugin(
        "multi-machine-training", "Train a model across multiple cloud machines", studio
    )

    plugin.run(command="python my-file.py", name="my-fancy-mmt-name", num_instances=42, cloud_compute=cloud_compute)


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_inference(
    internal_studio_init_mocker, internal_studio_status_mocker, internal_inference_run_mocker, cloud_compute
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    plugin = InferenceServerPlugin("inference-server", "Deploy an ML model accessible via API", studio)

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


def test_run_name():
    start_time = datetime.now().replace(second=0, microsecond=0)
    name = _run_name("fancy-abc")
    time_stamp_str = name.removeprefix("fancy-abc-")

    time_stamp = datetime.strptime(time_stamp_str, "%b-%d-%H_%M").replace(year=datetime.now().year)

    # assert this has the same time as current time and runs fast!
    assert start_time == time_stamp == datetime.now().replace(second=0, microsecond=0)
