import contextlib
import os
import subprocess

import pytest
from unittest import mock

from lightning_sdk.api.studio_api import StudioApi, _BYTES_PER_MB
from lightning_sdk.lightning_cloud.openapi import (
    V1CloudSpace,
    V1GetCloudSpaceInstanceStatusResponse,
)
from lightning_sdk.machine import Machine


def test_get_studio(internal_studio_api_mocker_get_studio):
    studio_api = StudioApi()
    studio = studio_api.get_studio("st-abc", "ts-abc")
    assert isinstance(studio, V1CloudSpace)


def test_get_studio_error(internal_studio_api_mocker_get_studio):
    studio_api = StudioApi()
    with pytest.raises(ValueError, match="Studio xyz does not exist"):
        studio_api.get_studio("xyz", "ts-abc")


@pytest.mark.parametrize("cluster", (None, "c-abc"))
def test_create_studio(internal_studio_api_mocker_create_studio, cluster):
    studio_api = StudioApi()
    studio = studio_api.create_studio("st-abc", "ts-abc", cluster=cluster)
    assert isinstance(studio, V1CloudSpace)
    assert studio.cluster_id == cluster


def test_get_studio_status(internal_studio_api_mocker_studio_status):
    studio_api = StudioApi()
    status = studio_api.get_studio_status("st-abc", "ts-abc")
    assert isinstance(status, V1GetCloudSpaceInstanceStatusResponse)


@pytest.mark.parametrize(
    "machine",
    (
        Machine.CPU,
        Machine.DATA_PREP,
        Machine.T4,
        Machine.T4_X_4,
        Machine.V100,
        Machine.V100_X_4,
        Machine.A10G,
        Machine.A10G_X_4,
        Machine.A100_X_8,
    ),
)
def test_switch_studio_machine(internal_studio_api_mocker_switch_machine, machine):
    studio_api = StudioApi()
    studio_api.switch_studio_machine("st-abc", "ts-abc", machine)


def test_switch_studio_machine_wrong_machine(internal_studio_api_mocker_switch_machine):
    studio_api = StudioApi()

    with pytest.raises(KeyError, match="foo"):
        studio_api.switch_studio_machine("st-abc", "ts-abc", "foo")


def test_start_studio(internal_studio_api_mocker_start_studio):
    studio_api = StudioApi()
    studio_api.start_studio("st-abc", "ts-abc", Machine.CPU)


def test_stop_studio(internal_studio_api_mocker_stop_studio, internal_studio_api_mocker_studio_status):
    studio_api = StudioApi()
    studio_api.stop_studio("st-abc", "ts-abc")


def test_run_command(internal_studio_api_mocker_run_command):
    studio_api = StudioApi()

    outputs, exit_code = studio_api.run_studio_commands("st-abc", "ts-abc", "foo", "bar")
    # explicitly no stripping on api level
    assert outputs == " foo-response bar-response "
    assert exit_code == 0


def test_delete_studio(internal_studio_api_mocker_delete):
    studio_api = StudioApi()

    studio_api.delete_studio("st-abc", "ts-abc")


@pytest.mark.parametrize(
    ("name", "expected_machine"),
    [
        ("st-abc", Machine.CPU),
        ("st-def", Machine.DATA_PREP),
        ("st-ghi", Machine.T4),
        ("st-jkl", Machine.T4_X_4),
        ("st-mno", Machine.V100),
        ("st-pqr", Machine.V100_X_4),
        ("st-stu", Machine.A10G),
        ("st-vwx", Machine.A10G_X_4),
        ("st-yza", Machine.A100_X_8),
    ],
)
def test_get_machine(internal_studio_api_mocker_get_machine, name, expected_machine):
    studio_api = StudioApi()

    machine = studio_api.get_machine(name, "ts-abc")

    assert isinstance(machine, Machine)
    assert expected_machine == machine


def test_duplicate_user(internal_studio_api_mocker_duplicate_user):
    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc")

    assert kwargs == {"name": "st-abc-de", "teamspace": "teamspace-abc", "user": "user-abc"}


def test_duplicate_org(internal_studio_api_mocker_duplicate_org):
    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc")

    assert kwargs == {"name": "st-abc-de", "teamspace": "teamspace-abc", "org": "org-abc"}


@pytest.mark.parametrize(
    "studio_id, expect_error, error_message, expect_info",
    [
        ("st-abc", False, "", ""),
        ("st-def", True, "abc", ""),
        ("st-ghi", True, "", ""),
        ("st-jkl", True, "jkl", ""),
        ("st-mno", False, "", "my-info"),
    ],
)
def test_install_plugin(internal_studio_api_install_plugin_mocker, studio_id, expect_error, error_message, expect_info):
    studio_api = StudioApi()

    if expect_error:
        context = pytest.raises(RuntimeError, match=f"Failed to install plugin my-fancy-plugin: {error_message}")
    else:
        context = contextlib.nullcontext()

    with context:
        add_info = studio_api.install_plugin(studio_id, "teamspace-abc", "my-fancy-plugin")

    if not expect_error:
        assert add_info == expect_info


@pytest.mark.parametrize(
    "studio_id, expect_error, error_message",
    [
        ("st-abc", False, ""),
        ("st-def", True, "abc"),
        ("st-ghi", True, ""),
        ("st-jkl", True, "jkl"),
    ],
)
def test_uninstall_plugin(internal_studio_api_uninstall_plugin_mocker, studio_id, expect_error, error_message):
    studio_api = StudioApi()

    if expect_error:
        context = pytest.raises(RuntimeError, match=f"Failed to uninstall plugin my-fancy-plugin: {error_message}")
    else:
        context = contextlib.nullcontext()

    with context:
        studio_api.uninstall_plugin(studio_id, "teamspace-abc", "my-fancy-plugin")


@pytest.mark.parametrize(
    "studio_id, expect_error, error_message, expected_port",
    [
        ("st-abc", False, "", 0),
        ("st-def", False, "", 1),
        ("st-ghi", False, "", -1),
        ("st-jkl", True, "jkl", None),
        ("st-mno", True, "", None),
        ("st-pqr", True, "pqr", None),
    ],
)
def test_execute_plugin(
    internal_studio_api_execute_plugin_mocker, studio_id, expect_error, error_message, expected_port
):
    studio_api = StudioApi()

    if expect_error:
        context = pytest.raises(RuntimeError, match=f"Failed to execute plugin my-fancy-plugin: {error_message}")
    else:
        context = contextlib.nullcontext()

    with context:
        output = studio_api.execute_plugin(studio_id, "teamspace-abc", "my-fancy-plugin")

    if not expect_error:
        output_str, port = output

        assert port == expected_port

        if port > 0:
            assert (
                output_str
                == f"Plugin my-fancy-plugin is interactive. Have a look at https://{expected_port}-{studio_id}.cloudspaces.litng.ai"
            )
        elif port == 0:
            assert output_str == "Successfully executed plugin my-fancy-plugin"
        elif port < 0:
            assert output_str == "This plugin can only be used on the browser interface of a Studio!"


def test_list_available_plugins(internal_studio_api_list_available_plugins_mocker):
    studio_api = StudioApi()

    plugins = studio_api.list_available_plugins("st-abc", "teamspace-abc")

    assert plugins == {"plugin1": "description1", "plugin2": "description2", "plugin3": "description3"}


def test_list_installed_plugins(internal_studio_api_list_installed_plugins_mocker):
    studio_api = StudioApi()

    plugins = studio_api.list_installed_plugins("st-abc", "teamspace-abc")

    assert plugins == {
        "plugin1": "description1",
        "plugin2": "description2",
    }


def test_create_job(internal_studio_api_create_app_mocker):
    studio_api = StudioApi()

    resp = studio_api.create_job("my-entry-point", "fancy-job-name", Machine.A10G, "st-abc", "ts-abc", "cluster-abc")
    assert resp.name == "fancy-job-name"


def test_create_mmt(internal_studio_api_create_app_mocker):
    studio_api = StudioApi()

    resp = studio_api.create_multi_machine_job(
        "my-entry-point", "fancy-mmt-name", 4, Machine.A10G, "parallel", "st-abc", "ts-abc", "cluster-abc"
    )
    assert resp.name == "fancy-mmt-name"


def test_create_inference_run(internal_studio_api_create_app_mocker):
    studio_api = StudioApi()

    resp = studio_api.create_inference_job(
        "my-entry-point",
        "fancy-inference-name",
        Machine.A10G,
        min_replicas="1",
        max_replicas="5",
        max_batch_size="10",
        timeout_batching="0.3",
        scale_in_interval="11",
        scale_out_interval="12",
        endpoint="/fancy-predict",
        studio_id="st-abc",
        teamspace_id="ts-abc",
        cluster_id="cluster-abc",
    )
    assert resp.name == "fancy-inference-name"


def test_upload_file_single_part(
    tmpdir, internal_studio_api_single_part_upload, internal_studio_api_requests_put_mocker
):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 1MB {filepath}".split(" "))

    studio_api.upload_file("st-abc", "ts-abc", "cluster-abc", filepath, "file1")


def test_upload_file_multi_part(tmpdir, internal_studio_api_multi_part_upload, internal_studio_api_requests_put_mocker):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 40MB {filepath}".split(" "))

    os.environ["LIGHTNING_MULTIPART_THRESHOLD"] = str(20 * _BYTES_PER_MB)
    studio_api.upload_file("st-abc", "ts-abc", "cluster-abc", filepath, "file1")


def test_download_file(tmpdir, internal_studio_api_login, internal_studio_api_requests_get_mocker):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_file("file1", filepath, "st-abc", "ts-abc", "cluster-abc")


@mock.patch("lightning_sdk.api.studio_api.zipfile")
def test_download_folder(_, tmpdir, internal_studio_api_login, internal_studio_api_requests_get_mocker):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_folder("file1", filepath, "st-abc", "ts-abc", "cluster-abc")
