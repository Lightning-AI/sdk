import os
import subprocess
from contextlib import nullcontext

import pytest

from lightning_sdk.machine import Machine
from lightning_sdk.plugin import (
    InferenceServerPlugin,
    JobsPlugin,
    MultiMachineTrainingPlugin,
    MultiMachineDataPrepPlugin,
    Plugin,
)
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio
from lightning_sdk.api.studio_api import _BYTES_PER_MB


@pytest.mark.parametrize("create_ok", [True, False])
@pytest.mark.parametrize("cluster", [None, "c-abc"])
@pytest.mark.parametrize("name", ["st-abc", "st-xyz"])
def test_studio_init(internal_studio_init_mocker, internal_studio_status_mocker, name, cluster, create_ok):
    # st-xyz does not exist and should not be created
    error_out = bool(name == "st-xyz" and not create_ok)
    contextman = pytest.raises(ValueError, match="Studio st-xyz does not exist") if error_out else nullcontext()

    with contextman:
        studio = Studio(name=name, teamspace="ts-abc", org="org-abc", cluster=cluster, create_ok=create_ok)

    if error_out:
        return

    assert studio.teamspace == "ts-abc"
    assert studio.owner == "org-abc"
    assert studio.name == name


@pytest.mark.parametrize(
    ("name", "expected_status"),
    [
        ("st-abc", Status.Pending),
        ("st-def", Status.Pending),
        ("st-ghi", Status.Running),
        ("st-jkl", Status.Failed),
        ("st-mno", Status.Stopping),
        ("st-pqr", Status.Stopped),
        ("st-stu", Status.Stopped),
    ],
)
def test_studio_status(internal_studio_status_mocker, internal_studio_init_mocker, name, expected_status):
    studio = Studio(name=name, teamspace="ts-abc", org="org-abc", create_ok=True)
    assert studio.status == expected_status


def test_studio_start(internal_studio_start_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None

    studio.start()

    assert studio.status == Status.Running
    assert studio.machine is not None


def test_studio_stop(internal_studio_stop_mocker, internal_studio_init_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Running

    studio.stop()

    assert studio.status == Status.Stopped


def test_studio_delete(internal_studio_delete_mocker, internal_studio_status_mocker):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc", create_ok=False)

    studio.delete()

    # doesn't exist anymore when deleted
    with pytest.raises(ValueError, match="Studio st-abc does not exist"):
        Studio(name="st-abc", teamspace="ts-abc", org="org-abc", create_ok=False)


@pytest.mark.parametrize(
    "target_machine",
    [
        Machine.CPU,
        Machine.DATA_PREP,
        Machine.T4,
        Machine.T4_X_4,
        Machine.V100,
        Machine.V100_X_4,
        Machine.A10G,
        Machine.A10G_X_4,
        Machine.A100_X_8,
    ],
)
def test_studio_switch_machine(internal_studio_switch_mocker, internal_studio_init_mocker, target_machine):
    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")

    assert studio.machine is None
    studio.start()

    assert studio.machine == Machine.CPU
    studio.switch_machine(target_machine)

    assert studio.machine == target_machine


def test_run_command(internal_studio_init_mocker, internal_studio_run_mocker):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.run("foo", "bar")

    assert result == "foo-response bar-response"


def test_run_command_error(internal_studio_init_mocker, internal_studio_run_error_mocker):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    with pytest.raises(RuntimeError, match="No such file or directory foo"):
        result = studio.run("foo", "bar")


def test_run_command_timeout(internal_studio_init_mocker, internal_studio_run_timeout_error_mocker):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    with pytest.raises(RuntimeError, match="Command execution timed out."):
        result = studio.run("foo", "bar")


def test_run_command_exit_code(internal_studio_init_mocker, internal_studio_run_mocker):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    result_output, result_exit_code = studio.run_with_exit_code("foo", "bar")

    assert result_output == "foo-response bar-response"
    assert result_exit_code == 0


@pytest.mark.parametrize(
    ("name", "expected_state", "forbidden_actions"),
    [
        ("st-def", Status.Pending, ["start", "switch", "run"]),
        ("st-jkl", Status.Failed, ["start", "stop", "switch", "run"]),
        ("st-mno", Status.Stopping, ["start", "switch", "run", "stop"]),
        ("st-pqr", Status.Stopped, ["stop", "switch", "run"]),
    ],
)
def test_action_in_wrong_state(
    internal_studio_init_mocker, internal_studio_status_mocker, name, expected_state, forbidden_actions
):
    studio = Studio(name, "ts-abc", "org-abc")
    assert studio.status == expected_state

    if "start" in forbidden_actions:
        with pytest.raises(
            RuntimeError, match=f"Cannot start a studio that is not stopped. Studio {name} is {expected_state}."
        ):
            studio.start()

    if "switch" in forbidden_actions:
        with pytest.raises(
            RuntimeError,
            match=f"Cannot switch machine on a studio that is not running. Studio {name} is {expected_state}.",
        ):
            studio.switch_machine(Machine.A10G)

    if "run" in forbidden_actions:
        with pytest.raises(
            RuntimeError,
            match=f"Cannot run a command in a studio that is not running. Studio {name} is {expected_state}.",
        ):
            studio.run("foo")

    if "stop" in forbidden_actions:
        with pytest.raises(
            RuntimeError, match=f"Cannot stop a studio that is not running. Studio {name} is {expected_state}"
        ):
            studio.stop()


def test_duplicate(internal_studio_init_mocker, internal_studio_duplicate_mocker):
    studio = Studio("st-abc", "ts-abc", "org-abc")
    studio.duplicate()


def test_install_plugin(
    internal_studio_init_plugin_mocker, internal_studio_status_mocker, internal_studio_plugin_install_mocker
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    assert not studio.installed_plugins

    studio.install_plugin("my-fancy-dummy-plugin")
    assert studio.installed_plugins == {
        "my-fancy-dummy-plugin": Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)
    }


def test_uninstall_plugin(
    internal_studio_init_plugin_mocker, internal_studio_status_mocker, internal_studio_plugin_uninstall_mocker
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    # check that all plugins that are claimed to be installed by the DB get actually installed
    assert studio.installed_plugins == {
        "my-fancy-dummy-plugin": Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)
    }

    studio.uninstall_plugin("my-fancy-dummy-plugin")
    assert not studio.installed_plugins

    assert not studio._list_installed_plugins()


def test_run_plugin(internal_studio_init_mocker, internal_studio_status_mocker, internal_studio_plugin_run_mocker):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    studio._plugins = {
        "my-fancy-dummy-plugin": Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)
    }

    studio.run_plugin("my-fancy-dummy-plugin")


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_job(internal_studio_init_mocker, internal_studio_status_mocker, internal_job_run_mocker, cloud_compute):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    studio._plugins = {
        "jobs": JobsPlugin(
            "jobs", "Launch asynchronous scripts from a Studio - Like submitting a job to a cluster", studio
        )
    }

    studio.run_plugin("jobs", command="python my-file.py", name="my-fancy-job-name", cloud_compute=cloud_compute)


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_mmt(internal_studio_init_mocker, internal_studio_status_mocker, internal_mmt_run_mocker, cloud_compute):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    studio._plugins = {
        "multi-machine-training": MultiMachineTrainingPlugin(
            "multi-machine-training", "Train a model across multiple cloud machines", studio
        )
    }

    studio.run_plugin(
        "multi-machine-training",
        command="python my-file.py",
        name="my-fancy-mmt-name",
        num_instances=42,
        cloud_compute=cloud_compute,
    )


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_data_prep(
    internal_studio_init_mocker, internal_studio_status_mocker, internal_data_prep_run_mocker, cloud_compute
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    studio._plugins = {
        "data-prep": MultiMachineDataPrepPlugin(
            "data-prep", "Transform large quantity of data using multiple cloud machines", studio
        )
    }

    studio.run_plugin(
        "data-prep",
        command="python my-file.py",
        name="my-fancy-data-prep-name",
        num_instances=42,
        cloud_compute=cloud_compute,
    )


@pytest.mark.parametrize("cloud_compute", Machine._member_map_.values())
def test_run_inference(
    internal_studio_init_mocker, internal_studio_status_mocker, internal_inference_run_mocker, cloud_compute
):
    studio = Studio("st-ghi", "ts-abc", "org-abc")
    studio._plugins = {
        "inference-server": InferenceServerPlugin("inference-server", "Deploy an ML model accessible via API", studio)
    }

    studio.run_plugin(
        "inference-server",
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


def test_upload_file_single_part(
    tmpdir, internal_studio_init_mocker, internal_studio_status_mocker, internal_studio_api_single_part_upload
):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 1MB {filepath}".split(" "))

    studio.upload_file(filepath, "file1")


def test_upload_file_multi_part(
    tmpdir, internal_studio_init_mocker, internal_studio_status_mocker, internal_studio_api_multi_part_upload
):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 40MB {filepath}".split(" "))

    os.environ["LIGHTNING_MULTIPART_THRESHOLD"] = str(20 * _BYTES_PER_MB)
    studio.upload_file(filepath, "file1")


def test_download_file(
    tmpdir,
    internal_studio_init_mocker,
    internal_studio_status_mocker,
    internal_studio_api_login,
    internal_studio_api_requests_get_mocker,
):
    studio = Studio("st-abc", "ts-abc", "org-abc")

    filepath = os.path.join(tmpdir, "file1")
    studio.download_file("file1", filepath)
