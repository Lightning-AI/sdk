import contextlib
import os
import subprocess
from unittest import mock

import pytest

from lightning_sdk.api import studio_api as studio_api_module
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.utils import _BYTES_PER_MB
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1CloudSpaceInstanceStartupStatus,
    V1CloudSpaceSeedFile,
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


@pytest.mark.parametrize("cloud_account", [None, "c-abc"])
@pytest.mark.parametrize("sandbox", [True, False])
@pytest.mark.parametrize("disable_secrets", [True, False])
def test_create_studio(internal_studio_api_mocker_create_studio, cloud_account, sandbox, disable_secrets):
    mock_create_cloud_space, _ = internal_studio_api_mocker_create_studio

    studio_api = StudioApi()
    studio = studio_api.create_studio(
        "st-abc", "ts-abc", cloud_account=cloud_account, sandbox=sandbox, disable_secrets=disable_secrets
    )
    assert isinstance(studio, V1CloudSpace)
    assert studio.cluster_id == cloud_account or ""

    mock_create_cloud_space.assert_called_once_with(
        mock.ANY,
        ProjectIdCloudspacesBody(
            cluster_id=cloud_account,
            name="st-abc",
            display_name="st-abc",
            seed_files=[V1CloudSpaceSeedFile(path="main.py", contents="print('Hello, Lightning World!')\n")],
            disable_secrets=disable_secrets,
            sandbox=sandbox,
        ),
        mock.ANY,
    )


def test_get_studio_status(internal_studio_api_mocker_studio_status):
    studio_api = StudioApi()
    status = studio_api.get_studio_status("st-abc", "ts-abc")
    assert isinstance(status, V1GetCloudSpaceInstanceStatusResponse)


@pytest.mark.parametrize(
    "machine",
    [
        Machine.CPU,
        Machine.DATA_PREP,
        Machine.T4,
        Machine.T4_X_4,
        Machine.L4,
        Machine.L4_X_4,
        Machine.A100_X_8,
        Machine.H100_X_8,
        Machine.H200_X_8,
        "trn1.2xlarge",
        Machine.CPU_SMALL,
        Machine.L4_X_2,
        Machine.A100_X_2,
        Machine.A100_X_4,
        Machine.B200_X_8,
    ],
)
def test_switch_studio_machine(internal_studio_api_mocker_switch_machine, machine):
    studio_api = StudioApi()
    studio_api.switch_studio_machine("st-abc", "ts-abc", machine, False)


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
    autospec=True,
)
def test_switch_machine_no_requested(_, __, status_mock):
    return_vals = [
        V1GetCloudSpaceInstanceStatusResponse(
            requested=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=False,
                    top_up_restore_finished=False,  # not yet restored anything
                )
            ),
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                )
            ),
        ),
        V1GetCloudSpaceInstanceStatusResponse(
            # doesn't return the requested instance -- possibly because it's not a requested instance anymore
            requested=None,
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                )
            ),
        ),
        V1GetCloudSpaceInstanceStatusResponse(
            requested=None,  # doesn't return the requested instance -- we switched already
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                )
            ),
        ),
    ]

    def side_effect(self, *args, **kwargs):
        if not return_vals:
            return V1GetCloudSpaceInstanceStatusResponse(
                requested=None,  # doesn't return the requested instance -- we switched already
                in_use=Externalv1CloudSpaceInstanceStatus(
                    startup_status=V1CloudSpaceInstanceStartupStatus(
                        initial_restore_finished=True, top_up_restore_finished=True
                    )
                ),
            )
        return return_vals.pop(0)

    status_mock.side_effect = side_effect
    studio_api = StudioApi()
    studio_api.switch_studio_machine("st-abc", "ts-abc", Machine.A100_X_8, False)


def test_start_studio(internal_studio_api_mocker_start_studio):
    studio_api = StudioApi()
    studio_api.start_studio("st-abc", "ts-abc", Machine.CPU, False)


def test_stop_studio(internal_studio_api_mocker_stop_studio, internal_studio_api_mocker_studio_status):
    studio_api = StudioApi()
    studio_api.stop_studio("st-abc", "ts-abc")


def test_run_command(internal_studio_api_mocker_run_command):
    studio_api = StudioApi()

    outputs, exit_code = studio_api.run_studio_commands("st-abc", "ts-abc", "foo", "bar")
    # explicitly no stripping on api level
    assert outputs == " foo-response bar-response "
    assert exit_code == 0

    from lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api import CloudSpaceServiceApi

    expected = {"project_id": "ts-abc", "id": "st-abc", "session": "session-name", "_preload_content": False}
    assert (
        CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream.mock_calls[0].kwargs
        == expected
    )


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
        ("st-mno", Machine.L4),
        ("st-pqr", Machine.L4_X_4),
        ("st-yza", Machine.A100_X_8),
        ("st-bcd", Machine.H100_X_8),
        ("st-efg", Machine.H200_X_8),
        ("st-hij", Machine.DATA_PREP_MAX),
        ("st-klm", Machine.DATA_PREP_ULTRA),
        ("st-tuv", Machine.L40S),
        ("st-wxy", Machine.L40S_X_4),
        ("st-zab", Machine.L40S_X_8),
        ("st-cde", Machine.L4_X_8),
        ("st-fgh", Machine.A100_X_2),
        ("st-ijk", Machine.A100_X_4),
        ("st-lmn", Machine.B200_X_8),
        ("st-opq", Machine.CPU_SMALL),
        ("st-rst", Machine.L4_X_2),
    ],
)
def test_get_machine(internal_studio_api_mocker_get_machine, name, expected_machine):
    studio_api = StudioApi()

    machine = studio_api.get_machine(name, "ts-abc", "cluster-abc", "test-org")

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
    ("studio_id", "expect_error", "error_message", "expect_info"),
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
    ("studio_id", "expect_error", "error_message"),
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
    ("studio_id", "expect_error", "error_message", "expected_port"),
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

    resp = studio_api.create_job(
        "my-entry-point", "fancy-job-name", Machine.L4, "st-abc", "ts-abc", "cluster-abc", False
    )
    assert resp.name == "fancy-job-name"


def test_create_job_with_service_id(monkeypatch):
    monkeypatch.setenv("LIGHTNING_SERVICE_EXECUTION_ID", "service_id")
    mock_client = mock.MagicMock()

    monkeypatch.setattr(studio_api_module, "LightningClient", mock.MagicMock(return_value=mock_client))
    studio_api = StudioApi()

    studio_api.create_job("my-entry-point", "fancy-job-name", Machine.L4, "st-abc", "ts-abc", "cluster-abc", False)
    assert (
        mock_client.cloud_space_service_create_cloud_space_app_instance._mock_mock_calls[0].kwargs["body"].service_id
        == "service_id"
    )


def test_create_mmt(internal_studio_api_create_app_mocker):
    studio_api = StudioApi()

    resp = studio_api.create_multi_machine_job(
        "my-entry-point", "fancy-mmt-name", 4, Machine.L4, "parallel", "st-abc", "ts-abc", "cluster-abc", False
    )
    assert resp.name == "fancy-mmt-name"


def test_create_inference_run(internal_studio_api_create_app_mocker):
    studio_api = StudioApi()

    resp = studio_api.create_inference_job(
        "my-entry-point",
        "fancy-inference-name",
        Machine.L4,
        min_replicas="1",
        max_replicas="5",
        max_batch_size="10",
        timeout_batching="0.3",
        scale_in_interval="11",
        scale_out_interval="12",
        endpoint="/fancy-predict",
        studio_id="st-abc",
        teamspace_id="ts-abc",
        cloud_account="cluster-abc",
        interruptible=False,
    )
    assert resp.name == "fancy-inference-name"


@pytest.mark.parametrize("progress_bar", [True, False])
@mock.patch("lightning_sdk.api.studio_api._FileUploader")
def test_upload_file(
    uploader_mock,
    tmpdir,
    progress_bar,
):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 40MB {filepath}".split(" "))

    os.environ["LIGHTNING_MULTIPART_THRESHOLD"] = str(20 * _BYTES_PER_MB)
    studio_api.upload_file("st-abc", "ts-abc", "cluster-abc", filepath, "file1", progress_bar=progress_bar)

    uploader_mock.assert_called_with(
        client=mock.ANY,
        file_path=filepath,
        remote_path="/cloudspaces/st-abc/code/content/file1",
        cloud_account="cluster-abc",
        teamspace_id="ts-abc",
        progress_bar=progress_bar,
    )
    uploader_mock().assert_called_with()  # .__call__()


def test_download_file(tmpdir, internal_studio_api_login, internal_studio_api_requests_get_mocker):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_file("file1", filepath, "st-abc", "ts-abc", "cluster-abc")


@mock.patch("lightning_sdk.api.studio_api.zipfile")
def test_download_folder(_, tmpdir, internal_studio_api_login, internal_studio_api_requests_get_mocker):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_folder("file1", filepath, "st-abc", "ts-abc", "cluster-abc")


def test_start_new_port(internal_studio_api_start_new_port_mocker):
    studio_api = StudioApi()

    url = studio_api.start_new_port("st-abc", "ts-abc", "test", 8000)

    assert url == "http://localhost:8000", "endpoint_service_create_endpoint returns [localhost:8000] for urls"
