import os
import subprocess
import warnings
from unittest import mock

import pytest

from lightning_sdk.api import studio_api as studio_api_module
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceCreateCloudSpaceBody,
    Externalv1CloudSpaceInstanceStatus,
    Externalv1LightningappInstance,
    V1AWSDirectV1,
    V1CloudProvider,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceInstanceStartupStatus,
    V1CloudSpaceSeedFile,
    V1CloudSpaceState,
    V1ClusterAccelerator,
    V1ClusterType,
    V1CreateCloudSpaceAppInstanceResponse,
    V1DeleteCloudSpaceResponse,
    V1Endpoint,
    V1ExecuteCloudSpaceCommandResponse,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetUserResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListClustersResponse,
    V1ListDefaultClusterAcceleratorsResponse,
    V1ListEndpointsResponse,
    V1ListProjectClustersResponse,
    V1Organization,
    V1Project,
    V1Resources,
    V1SearchUser,
    V1SearchUsersResponse,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.machine import Machine


class _DummyResponse:
    data: bytes


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_studio(mock_list_cloudspaces):
    def list_cloudspaces_side_effect(self, project_id, name):
        if name in ["st-abc", "st-def"]:
            return V1ListCloudSpacesResponse([V1CloudSpace(name=name, display_name=name)])
        return V1ListCloudSpacesResponse([])

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect

    studio_api = StudioApi()
    studio = studio_api.get_studio("st-abc", "ts-abc")
    assert isinstance(studio, V1CloudSpace)


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_studio_error(mock_list_cloudspaces):
    def list_cloudspaces_side_effect(self, project_id, name):
        if name in ["st-abc", "st-def"]:
            return V1ListCloudSpacesResponse([V1CloudSpace(name=name, display_name=name)])
        return V1ListCloudSpacesResponse([])

    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect

    studio_api = StudioApi()
    with pytest.raises(ValueError, match="Studio xyz does not exist"):
        studio_api.get_studio("xyz", "ts-abc")


@pytest.mark.parametrize("cloud_account", [None, "c-abc"])
@pytest.mark.parametrize("sandbox", [True, False])
@pytest.mark.parametrize("disable_secrets", [True, False])
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_create_studio(mock_create_cloud_space, mock_create_lightning_run, _, cloud_account, sandbox, disable_secrets):
    def _create_cloudspace_side_effect(self, body, project_id, **kwargs):
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        return V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )

    def _create_lightning_run_side_effect(self, body, project_id, cloudspace_id, **kwargs):
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    mock_create_cloud_space.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect

    studio_api = StudioApi()
    studio = studio_api.create_studio(
        "st-abc", "ts-abc", cloud_account=cloud_account, sandbox=sandbox, disable_secrets=disable_secrets
    )
    assert isinstance(studio, V1CloudSpace)
    assert studio.cluster_id == cloud_account or ""

    mock_create_cloud_space.assert_called_once_with(
        mock.ANY,
        CloudSpaceServiceCreateCloudSpaceBody(
            cluster_id=cloud_account,
            name="st-abc",
            display_name="st-abc",
            seed_files=[V1CloudSpaceSeedFile(path="main.py", contents="print('Hello, Lightning World!')\n")],
            disable_secrets=disable_secrets,
            sandbox=sandbox,
        ),
        mock.ANY,
    )


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_studio_status(mock_get_status):
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(initial_restore_finished=False)
        )
    )

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
        Machine.T4_SMALL,
    ],
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_switch_studio_machine(mock_get_status, mock_update_config, mock_switch_instance, machine):
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
    )

    studio_api = StudioApi()
    studio_api.switch_studio_machine("st-abc", "ts-abc", machine, False, None)


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
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_switch_machine_no_requested(switch_mock, update_mock, status_mock):
    return_vals = [
        # First call: there is a requested machine (we just made the request)
        V1GetCloudSpaceInstanceStatusResponse(
            requested=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                )
            ),
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=False, top_up_restore_finished=False
                )
            ),
        ),
        # Second call: requested is now None (processed), but in_use is ready for switch
        V1GetCloudSpaceInstanceStatusResponse(
            requested=None,  # Request was processed, no longer pending
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                )
            ),
        ),
        # Third call: after switch, new machine is ready
        V1GetCloudSpaceInstanceStatusResponse(
            requested=None,
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                )
            ),
        ),
    ]

    def side_effect(*args, **kwargs):
        if not return_vals:
            return V1GetCloudSpaceInstanceStatusResponse(
                requested=None,
                in_use=Externalv1CloudSpaceInstanceStatus(
                    startup_status=V1CloudSpaceInstanceStartupStatus(
                        initial_restore_finished=True, top_up_restore_finished=True
                    )
                ),
            )
        return return_vals.pop(0)

    status_mock.side_effect = side_effect
    studio_api = StudioApi()
    studio_api.switch_studio_machine("st-abc", "ts-abc", Machine.A100_X_8, False, None)


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_start_studio(mock_start_instance, mock_get_status):
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
    )

    studio_api = StudioApi()
    studio_api.start_studio("st-abc", "ts-abc", Machine.CPU, False)


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_stop_cloud_space_instance",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_stop_studio(mock_stop_instance, mock_get_status):
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(initial_restore_finished=False)
        )
    )

    studio_api = StudioApi()
    studio_api.stop_studio("st-abc", "ts-abc")


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_run_command(mock_execute_command, mock_get_stream):
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(
        exit_code=0, output="Command Started Successfully", session_name="session-name"
    )

    resp = _DummyResponse()
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    studio_api = StudioApi()

    outputs, exit_code = studio_api.run_studio_commands("st-abc", "ts-abc", "foo", "bar")
    # explicitly no stripping on api level
    assert outputs == " foo-response bar-response "
    assert exit_code == 0

    expected = {"project_id": "ts-abc", "id": "st-abc", "session": "session-name", "_preload_content": False}
    assert mock_get_stream.mock_calls[0].kwargs == expected


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_delete_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_delete_studio(mock_delete_cloud_space):
    mock_delete_cloud_space.return_value = V1DeleteCloudSpaceResponse()

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
        ("st-uvw", Machine.T4_SMALL),
    ],
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_default_cluster_accelerators",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_machine(
    mock_list_project_clusters, mock_list_clusters, mock_list_accelerators, mock_get_config, name, expected_machine
):
    # Setup machine config mocker side effect
    studio_to_machine_map = {
        "st-abc": "cpu-4",
        "st-def": "data-large",
        "st-ghi": "g4dn.2xlarge",
        "st-jkl": "g4dn.12xlarge",
        "st-mno": "g6.4xlarge",
        "st-pqr": "g6.12xlarge",
        "st-yza": "p4d.24xlarge",
        "st-bcd": "p5.48xlarge",
        "st-efg": "p5en.48xlarge",
        "st-hij": "data-max",
        "st-klm": "data-ultra",
        "st-nop": "m3.medium",
        "st-tuv": "g6e.4xlarge",
        "st-wxy": "g6e.12xlarge",
        "st-zab": "g6e.48xlarge",
        "st-cde": "g6.48xlarge",
        "st-fgh": "a2-ultragpu-2g",
        "st-ijk": "a2-ultragpu-4g",
        "st-lmn": "a4-highgpu-8g",
        "st-opq": "n2d-standard-2",
        "st-rst": "g2-standard-24",
        "st-uvw": "lit-t4-1-small",
    }

    def _side_effect(self, project_id, id, **kwargs):
        instance_type_str = studio_to_machine_map.get(id)
        if instance_type_str is None:
            raise ValueError(f"No machine found for studio ID: {id}")
        return V1CloudSpaceInstanceConfig(compute_config=V1UserRequestedComputeConfig(name=instance_type_str))

    mock_get_config.side_effect = _side_effect

    # Create test cloud accounts for different cluster_ids used in tests
    test_cloud_accounts = [
        V1ExternalCluster(
            id="cluster_abc",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
        V1ExternalCluster(
            id="c-abc",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
        V1ExternalCluster(
            id="cluster-abc",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
        V1ExternalCluster(
            id="my-preferred-cluster",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
        V1ExternalCluster(
            id=None,
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
    ]

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=test_cloud_accounts)
    mock_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                instance_id="cpu-4",
                slug_multi_cloud="cpu-4",
                enabled=True,
                resources=V1Resources(cpu=4),
                family="CPU",
                accelerator_type="CPU",
            ),
            V1ClusterAccelerator(
                instance_id="data-large",
                slug_multi_cloud="data-prep-mid",
                enabled=True,
                resources=V1Resources(cpu=32),
                family="DATA_PREP",
                accelerator_type="CPU",
            ),
            V1ClusterAccelerator(
                instance_id="g4dn.2xlarge",
                slug_multi_cloud="lit-t4-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="T4",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="g4dn.12xlarge",
                slug_multi_cloud="lit-t4-4",
                enabled=True,
                resources=V1Resources(gpu=4),
                family="L4",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="g6.4xlarge",
                slug_multi_cloud="lit-l4-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="L4",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="g6.12xlarge",
                slug_multi_cloud="lit-l4-4",
                enabled=True,
                resources=V1Resources(gpu=4),
                family="L4",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="p4d.24xlarge",
                slug_multi_cloud="lit-a100-8",
                enabled=True,
                resources=V1Resources(gpu=8),
                family="A100",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="p5.48xlarge",
                slug_multi_cloud="lit-h100-8",
                enabled=True,
                resources=V1Resources(gpu=8),
                family="H100",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="p5en.48xlarge",
                slug_multi_cloud="lit-h200x-8",
                enabled=True,
                resources=V1Resources(gpu=8),
                family="H200",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="data-max",
                slug_multi_cloud="data-prep-max-large",
                enabled=True,
                resources=V1Resources(cpu=64),
                family="DATA_PREP",
            ),
            V1ClusterAccelerator(
                instance_id="data-ultra",
                slug_multi_cloud="data-prep-ultra-extra-large",
                enabled=True,
                resources=V1Resources(cpu=96),
                family="DATA_PREP",
                accelerator_type="CPU",
            ),
            V1ClusterAccelerator(
                instance_id="m3.medium",
                slug_multi_cloud="cpu-2",
                enabled=True,
                resources=V1Resources(cpu=2),
                family="CPU",
                accelerator_type="CPU",
            ),
            V1ClusterAccelerator(
                instance_id="g6e.4xlarge",
                slug_multi_cloud="lit-l40s-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="L40S",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="g6e.12xlarge",
                slug_multi_cloud="lit-l40s-4",
                enabled=True,
                resources=V1Resources(gpu=4),
                family="L40S",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="g6e.48xlarge",
                slug_multi_cloud="lit-l40s-8",
                enabled=True,
                resources=V1Resources(gpu=8),
                family="L40S",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="g6.48xlarge",
                slug_multi_cloud="lit-l4-8",
                enabled=True,
                resources=V1Resources(gpu=8),
                family="L4",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="a2-ultragpu-2g",
                slug_multi_cloud="lit-a100-2",
                enabled=True,
                resources=V1Resources(gpu=2),
                family="A100",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="a2-ultragpu-4g",
                slug_multi_cloud="lit-a100-4",
                enabled=True,
                resources=V1Resources(gpu=4),
                family="A100",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="a4-highgpu-8g",
                slug_multi_cloud="lit-b200x-8",
                enabled=True,
                resources=V1Resources(gpu=8),
                family="B200",
                accelerator_type="GPU",
            ),
            V1ClusterAccelerator(
                instance_id="n2d-standard-2",
                slug_multi_cloud="cpu-2",
                enabled=True,
                resources=V1Resources(cpu=2),
                family="CPU",
                accelerator_type="CPU",
            ),
            V1ClusterAccelerator(
                instance_id="g2-standard-24",
                slug_multi_cloud="lit-l4-2",
                enabled=True,
                resources=V1Resources(gpu=2),
                family="L4",
                accelerator_type="GPU",
            ),
        ]
    )

    studio_api = StudioApi()

    machine = studio_api.get_machine(name, "ts-abc", "cluster-abc", "test-org")

    assert isinstance(machine, Machine)

    print(machine)
    print(expected_machine)
    assert expected_machine == machine


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_get_user", autospec=True
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.user_service_api.UserServiceApi.user_service_search_users", autospec=True
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_duplicate_user(
    mock_get_project,
    mock_search_users,
    mock_get_user,
    mock_get_status,
    mock_start_instance,
    mock_get_cloudspace,
    mock_fork_cloudspace,
):
    mock_get_project.return_value = V1Project(
        id="ts-abc", name="teamspace-abc", display_name="Teamspace ABC", owner_id="user-abc", owner_type="user"
    )
    mock_search_users.return_value = V1SearchUsersResponse(users=[V1SearchUser(id="user-abc", username="user-abc")])
    mock_get_user.return_value = V1GetUserResponse(id="user-abc", username="user-abc")
    mock_fork_cloudspace.return_value = V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de")
    mock_get_cloudspace.return_value = V1CloudSpace(
        name="st-abc-de", display_name="st-abc-de", id="st-abc-de", state=V1CloudSpaceState.READY
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )

    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc")

    assert kwargs == {"name": "st-abc-de", "teamspace": "teamspace-abc", "user": "user-abc"}


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_duplicate_org(
    mock_get_project,
    mock_get_org,
    mock_get_status,
    mock_start_instance,
    mock_get_cloudspace,
    mock_fork_cloudspace,
):
    mock_get_project.return_value = V1Project(
        id="ts-abc",
        name="teamspace-abc",
        display_name="Teamspace ABC",
        owner_id="org-abc",
        owner_type="organization",
    )
    mock_get_org.return_value = V1Organization(name="org-abc", display_name="org-abc", id="org-abc")
    mock_fork_cloudspace.return_value = V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de")
    mock_get_cloudspace.return_value = V1CloudSpace(
        name="st-abc-de",
        display_name="st-abc-de",
        id="st-abc-de",
        state=V1CloudSpaceState.READY,
        cluster_id="c-abc",
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )

    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc")

    assert kwargs == {"name": "st-abc-de", "teamspace": "teamspace-abc", "org": "org-abc"}


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_get_user", autospec=True
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.user_service_api.UserServiceApi.user_service_search_users", autospec=True
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_duplicate_user_with_new_name(
    mock_get_project,
    mock_search_users,
    mock_get_user,
    mock_get_status,
    mock_start_instance,
    mock_get_cloudspace,
    mock_fork_cloudspace,
):
    mock_get_project.return_value = V1Project(
        id="ts-abc", name="teamspace-abc", display_name="Teamspace ABC", owner_id="user-abc", owner_type="user"
    )
    mock_search_users.return_value = V1SearchUsersResponse(users=[V1SearchUser(id="user-abc", username="user-abc")])
    mock_get_user.return_value = V1GetUserResponse(id="user-abc", username="user-abc")
    mock_fork_cloudspace.return_value = V1CloudSpace(
        name="my-custom-studio", display_name="my-custom-studio", id="st-custom"
    )
    mock_get_cloudspace.return_value = V1CloudSpace(
        name="my-custom-studio", display_name="my-custom-studio", id="st-custom", state=V1CloudSpaceState.READY
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )

    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc", new_name="my-custom-studio")

    mock_fork_cloudspace.assert_called_once()
    call_args = mock_fork_cloudspace.call_args
    body = call_args[0][1]
    assert body.new_name == "my-custom-studio"
    assert kwargs == {"name": "my-custom-studio", "teamspace": "teamspace-abc", "user": "user-abc"}


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_duplicate_org_with_new_name(
    mock_get_project,
    mock_get_org,
    mock_get_status,
    mock_start_instance,
    mock_get_cloudspace,
    mock_fork_cloudspace,
):
    mock_get_project.return_value = V1Project(
        id="ts-abc",
        name="teamspace-abc",
        display_name="Teamspace ABC",
        owner_id="org-abc",
        owner_type="organization",
    )
    mock_get_org.return_value = V1Organization(name="org-abc", display_name="org-abc", id="org-abc")
    mock_fork_cloudspace.return_value = V1CloudSpace(
        name="renamed-studio", display_name="renamed-studio", id="st-renamed"
    )
    mock_get_cloudspace.return_value = V1CloudSpace(
        name="renamed-studio",
        display_name="renamed-studio",
        id="st-renamed",
        state=V1CloudSpaceState.READY,
        cluster_id="c-abc",
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )

    studio_api = StudioApi()
    kwargs = studio_api.duplicate_studio("st-abc", "ts-abc", "ts-abc", new_name="renamed-studio")

    mock_fork_cloudspace.assert_called_once()
    call_args = mock_fork_cloudspace.call_args
    body = call_args[0][1]
    assert body.new_name == "renamed-studio"
    assert kwargs == {"name": "renamed-studio", "teamspace": "teamspace-abc", "org": "org-abc"}


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
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


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_create_inference_run(mock_create_app):
    def side_effect(self, body, project_id, cloudspace_id, id):
        if id == "inference_plugin":
            assert body.plugin_arguments == {
                "compute": "lit-l4-1",
                "entrypoint": "my-entry-point",
                "name": "fancy-inference-name",
                "min_replicas": "1",
                "max_replicas": "5",
                "max_batch_size": "10",
                "timeout_batching": "0.3",
                "scale_in_interval": "11",
                "scale_out_interval": "12",
                "endpoint": "/fancy-predict",
                "spot": "false",
            }

        return V1CreateCloudSpaceAppInstanceResponse(
            lightningappinstance=Externalv1LightningappInstance(name=body.plugin_arguments["name"])
        )

    mock_create_app.side_effect = side_effect

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


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="test-token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_tree(mock_authenticate, mock_requests_get):
    """Test get_tree retrieves directory structure from studio."""
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {
        "tree": [
            {"path": "file1.txt", "type": "blob", "size": 1234},
            {"path": "folder1", "type": "tree"},
            {"path": "file2.py", "type": "blob", "size": 5678},
        ],
        "truncated": False,
    }
    mock_requests_get.return_value = mock_response

    studio_api = StudioApi()

    result = studio_api.get_tree("st-abc", "ts-abc", "my-folder/")

    assert result == {
        "tree": [
            {"path": "file1.txt", "type": "blob", "size": 1234},
            {"path": "folder1", "type": "tree"},
            {"path": "file2.py", "type": "blob", "size": 5678},
        ],
        "truncated": False,
    }

    mock_requests_get.assert_called_once()
    call_args = mock_requests_get.call_args

    assert "/v1/projects/ts-abc/artifacts/cloudspaces/st-abc/trees/my-folder/" in call_args[0][0]
    assert call_args[1]["params"] == {"token": "test-token"}
    mock_authenticate.assert_called_once_with(studio_api._client)


@pytest.mark.parametrize(
    ("path", "tree_response", "expected_result"),
    [
        (
            "",
            None,
            {"exists": True, "type": "directory", "size": None},
        ),
        # file exists
        (
            "test.txt",
            {"tree": [{"path": "test.txt", "type": "blob", "size": 1024}]},
            {"exists": True, "type": "file", "size": 1024},
        ),
        # directory exists
        (
            "test-dir",
            {"tree": [{"path": "test-dir", "type": "tree"}]},
            {"exists": True, "type": "directory", "size": None},
        ),
        # Test case 3: File does not exist (empty tree)
        (
            "nonexistent.txt",
            {"tree": []},
            {"exists": False, "type": None, "size": None},
        ),
        # nested file
        (
            "path/to/data.csv",
            {"tree": [{"path": "data.csv", "type": "blob", "size": 2048}]},
            {"exists": True, "type": "file", "size": 2048},
        ),
        # nested directory
        (
            "path/to/subfolder",
            {"tree": [{"path": "subfolder", "type": "tree"}]},
            {"exists": True, "type": "directory", "size": None},
        ),
    ],
)
@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="test-token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_path_info(mock_authenticate, mock_requests_get, path, tree_response, expected_result):
    mock_response = mock.MagicMock()
    mock_response.json.return_value = tree_response
    mock_requests_get.return_value = mock_response

    studio_api = StudioApi()

    if not expected_result["exists"]:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = studio_api.get_path_info("st-abc", "ts-abc", path)

            # Check warning was raised
            assert len(w) == 1
            assert "may be empty" in str(w[0].message)
    else:
        result = studio_api.get_path_info("st-abc", "ts-abc", path)

    assert result == expected_result

    if path.strip("/") == "":
        mock_requests_get.assert_not_called()
        mock_authenticate.assert_not_called()
    else:
        if "/" in path:
            expected_parent = path.rsplit("/", 1)[0]
            assert expected_parent in mock_requests_get.call_args[0][0]
        else:
            # root level should include /trees/
            call_url = mock_requests_get.call_args[0][0]
            assert "/trees/" in call_url
        mock_authenticate.assert_called_once_with(studio_api._client)


@pytest.mark.parametrize(
    ("path", "mock_response", "expected_files"),
    [
        # nested directories with multiple levels
        (
            "my-folder",
            {
                "tree": [
                    {"path": "file1.txt", "type": "blob"},
                    {"path": "folder1/nested.txt", "type": "blob", "size": 999},
                    {"path": "folder1/subfolder/deep.txt", "type": "blob", "size": 111},
                    {"path": "file2.py", "type": "blob"},
                ],
                "truncated": False,
            },
            [
                {"path": "file1.txt", "type": "blob"},
                {"path": "folder1/nested.txt", "type": "blob", "size": 999},
                {"path": "folder1/subfolder/deep.txt", "type": "blob", "size": 111},
                {"path": "file2.py", "type": "blob"},
            ],
        ),
        # empty directory
        (
            "empty-folder",
            {
                "tree": [],
                "truncated": False,
            },
            [],
        ),
        # root path (empty string)
        (
            "",
            {
                "tree": [
                    {"path": "root-file.txt", "type": "blob", "size": 100},
                ],
                "truncated": False,
            },
            [
                {"path": "root-file.txt", "type": "blob", "size": 100},
            ],
        ),
        # path with leading/trailing slashes
        (
            "/my-folder/",
            {
                "tree": [
                    {"path": "file.txt", "type": "blob"},
                ],
                "truncated": False,
            },
            [
                {"path": "file.txt", "type": "blob"},
            ],
        ),
    ],
)
@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="test-token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_files(
    mock_authenticate,
    mock_requests_get,
    path,
    mock_response,
    expected_files,
):
    """Test that list_files correctly calls get_tree with recursive=true."""
    studio_api = StudioApi()
    mock_response_obj = mock.MagicMock()
    mock_response_obj.json.return_value = mock_response
    mock_requests_get.return_value = mock_response_obj

    result = studio_api.list_files(
        studio_id="st-abc",
        teamspace_id="ts-abc",
        path=path,
    )

    assert mock_requests_get.call_count == 1
    call_args = mock_requests_get.call_args

    # get_tree
    host = studio_api._client.api_client.configuration.host
    expected_url = f"{host}/v1/projects/ts-abc/artifacts/cloudspaces/st-abc/trees/{path.strip('/')}"
    assert call_args[0][0] == expected_url

    # recursive
    assert call_args[1]["params"]["recursive"] == "true"

    assert result == expected_files
    mock_authenticate.assert_called_once_with(studio_api._client)


def _blob_upload_create_response(path, upload_id, urls):
    response = mock.Mock(status_code=200)
    response.json.return_value = {
        "expires_at": "2026-01-01T00:00:00Z",
        "results": [{"path": path, "upload_id": upload_id, "urls": urls}],
    }
    return response


@pytest.mark.parametrize("progress_bar", [True, False])
@pytest.mark.parametrize("file_size_mb", [4, 200])  # 4MB for single-part, 200MB for multipart
@mock.patch("requests.post")
@mock.patch("requests.put")
@mock.patch("lightning_sdk.api.utils.tqdm")
@mock.patch("lightning_sdk.api.utils._authenticate_and_get_token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_upload_file(
    authenticate_mock,
    tqdm_mock,
    requests_put_mock,
    requests_post_mock,
    tmpdir,
    progress_bar,
    file_size_mb,
    monkeypatch,
):
    # the autouse keep_alive_mocker fixture mocks threading.Thread, so real
    # executor workers would never run; fall back to a plain map
    monkeypatch.setattr("lightning_sdk.api.utils.ThreadPoolExecutor.map", map)
    tqdm_mock.wrapattr.side_effect = lambda f, *args, **kwargs: f
    authenticate_mock.return_value = "test-token-123"

    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s {file_size_mb}MB {filepath}".split(" "))

    single_part = file_size_mb <= 100
    urls = (
        [{"url": "https://storage.example.com/signed"}]
        if single_part
        else [
            {"url": "https://storage.example.com/part1", "part_number": 1},
            {"url": "https://storage.example.com/part2", "part_number": 2},
        ]
    )
    requests_post_mock.side_effect = [
        _blob_upload_create_response("file1", "" if single_part else "upload-1", urls),
        mock.Mock(status_code=204),
    ]
    requests_put_mock.return_value = mock.Mock(status_code=200, headers={"ETag": "etag-1"})

    studio_api.upload_file("st-abc", "ts-abc", "cluster-abc", filepath, "file1", progress_bar=progress_bar)

    # URL request and completion both go to the studio-scoped batch endpoints,
    # with the blob path in the body rather than the URL.
    create_call = requests_post_mock.call_args_list[0]
    assert create_call.args[0].endswith("/v1/projects/ts-abc/artifacts/cloudspaces/st-abc/blobs")
    assert create_call.kwargs["params"] == {"token": "test-token-123"}
    complete_call = requests_post_mock.call_args_list[1]
    assert complete_call.args[0].endswith("/v1/projects/ts-abc/artifacts/cloudspaces/st-abc/blobs/complete")
    assert complete_call.kwargs["params"] == {"token": "test-token-123"}

    if single_part:
        assert create_call.kwargs["json"] == {"blobs": [{"path": "file1"}]}
        assert complete_call.kwargs["json"] == {"blobs": [{"path": "file1"}]}

        assert requests_put_mock.call_count == 1
        assert requests_put_mock.call_args.args[0] == "https://storage.example.com/signed"

        if progress_bar:
            tqdm_mock.wrapattr.assert_called_once()
        else:
            tqdm_mock.wrapattr.assert_not_called()
    else:
        assert create_call.kwargs["json"] == {"blobs": [{"path": "file1", "parts": 2, "part_size": 100_000_000}]}

        assert requests_put_mock.call_count == 2
        put_urls = sorted(c.args[0] for c in requests_put_mock.call_args_list)
        assert put_urls == ["https://storage.example.com/part1", "https://storage.example.com/part2"]

        completed = complete_call.kwargs["json"]["blobs"][0]
        assert completed["path"] == "file1"
        assert completed["upload_id"] == "upload-1"
        assert [p["part_number"] for p in completed["parts"]] == [1, 2]
        assert all(p["etag"] == "etag-1" for p in completed["parts"])


@pytest.mark.parametrize("remote_path", ["/home/zeus/content/file1.tar.gz", "home/zeus/content/file1.tar.gz"])
@mock.patch("requests.post")
@mock.patch("requests.put")
@mock.patch("lightning_sdk.api.utils.tqdm")
@mock.patch("lightning_sdk.api.utils._authenticate_and_get_token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_upload_file_leading_slash(
    authenticate_mock,
    tqdm_mock,
    requests_put_mock,
    requests_post_mock,
    tmpdir,
    remote_path,
):
    # A leading slash must not leak into the blob path sent to the upload
    # endpoints; both variants request the same clean path.
    tqdm_mock.wrapattr.side_effect = lambda f, *args, **kwargs: f
    authenticate_mock.return_value = "test-token-123"

    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    subprocess.run(f"truncate -s 4MB {filepath}".split(" "))

    requests_post_mock.side_effect = [
        _blob_upload_create_response("home/zeus/content/file1.tar.gz", "", [{"url": "https://storage.example.com/s"}]),
        mock.Mock(status_code=204),
    ]
    requests_put_mock.return_value = mock.Mock(status_code=200)

    studio_api.upload_file("st-abc", "ts-abc", "cluster-abc", filepath, remote_path, progress_bar=False)

    create_call = requests_post_mock.call_args_list[0]
    assert create_call.kwargs["json"] == {"blobs": [{"path": "home/zeus/content/file1.tar.gz"}]}
    complete_call = requests_post_mock.call_args_list[1]
    assert complete_call.kwargs["json"] == {"blobs": [{"path": "home/zeus/content/file1.tar.gz"}]}


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_download_file(mock_authenticate, mock_requests_get, tmpdir):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": "1024"}
    mock_response.iter_content = mock.Mock(return_value=[b"data" * 256])
    mock_requests_get.return_value = mock_response

    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_file("file1", filepath, "st-abc", "ts-abc", "cluster-abc")
    mock_authenticate.assert_called_once_with(studio_api._client)


@mock.patch("requests.get", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_download_file_non_200_status(mock_authenticate, mock_requests_get, tmpdir):
    mock_response = mock.Mock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    studio_api = StudioApi()
    filepath = os.path.join(tmpdir, "file1")

    with pytest.raises(RuntimeError, match="Failed to download file: 404"):
        studio_api.download_file("file1", filepath, "st-abc", "ts-abc", "cluster-abc")

    assert not os.path.exists(filepath)
    mock_authenticate.assert_called_once_with(studio_api._client)


@mock.patch("lightning_sdk.api.studio_api.concurrent.futures.wait")
@mock.patch("lightning_sdk.api.studio_api.tqdm")
@mock.patch("lightning_sdk.api.studio_api.ThreadPoolExecutor")
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_download_folder(authenticate_mock, mock_executor, mock_tqdm, mock_wait, tmpdir):
    authenticate_mock.return_value = "test-token-123"

    studio_api = StudioApi()

    studio_api.list_files = mock.Mock(
        return_value=[
            {"path": "file1.txt", "size": 1000},
            {"path": "file2.txt", "size": 2000},
        ]
    )

    studio_api._download_single_studio_file = mock.Mock()

    mock_future = mock.Mock()
    mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future
    mock_wait.return_value = None

    filepath = os.path.join(tmpdir, "download_folder")
    studio_api.download_folder("file1", filepath, "st-abc", "ts-abc", "cluster-abc")

    studio_api.list_files.assert_called_once_with("st-abc", "ts-abc", "file1")

    mock_executor.assert_called_once()

    mock_tqdm.assert_called_once()
    assert mock_tqdm.call_args.kwargs["desc"] == "Downloading files"
    assert mock_tqdm.call_args.kwargs["total"] == 3000  # 1000 + 2000


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_create_endpoint",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_add_ports(mock_create_endpoint):
    mock_create_endpoint.return_value = V1Endpoint(
        id="endpoint-id",
        name="endpoint-name",
        urls=["http://localhost:8000"],
    )

    studio_api = StudioApi()

    endpoint = studio_api.add_port("st-abc", "ts-abc", "test", 8000)
    url = endpoint.urls[0]

    assert url == "http://localhost:8000", "endpoint_service_create_endpoint returns [localhost:8000] for urls"


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_sleep_config",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_update_autoshutdown_auto_sleep_on(mock_update_sleep_config):
    def response(self, id, project_id, body):
        if id == "st-abc":
            if (
                body.disable_auto_shutdown is not None
                and body.idle_shutdown_seconds is not None
                and body.idle_shutdown_seconds > 0
            ):
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=body.disable_auto_shutdown, idle_shutdown_seconds=body.idle_shutdown_seconds
                )

            if body.idle_shutdown_seconds is not None and body.idle_shutdown_seconds > 0:
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=False, idle_shutdown_seconds=body.idle_shutdown_seconds
                )

            if body.disable_auto_shutdown is not None:
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=body.disable_auto_shutdown, idle_shutdown_seconds=600
                )
        return V1CloudSpaceInstanceConfig(disable_auto_shutdown=None, idle_shutdown_seconds=600)

    mock_update_sleep_config.side_effect = response

    studio_api = StudioApi()

    config = studio_api.update_autoshutdown(studio_id="st-abc", teamspace_id="ts-abc", enabled=True)
    assert config.disable_auto_shutdown is False
    assert config.idle_shutdown_seconds == 600


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_sleep_config",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_update_autoshutdown_auto_sleep_off(mock_update_sleep_config):
    def response(self, id, project_id, body):
        if id == "st-abc":
            if (
                body.disable_auto_shutdown is not None
                and body.idle_shutdown_seconds is not None
                and body.idle_shutdown_seconds > 0
            ):
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=body.disable_auto_shutdown, idle_shutdown_seconds=body.idle_shutdown_seconds
                )

            if body.idle_shutdown_seconds is not None and body.idle_shutdown_seconds > 0:
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=False, idle_shutdown_seconds=body.idle_shutdown_seconds
                )

            if body.disable_auto_shutdown is not None:
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=body.disable_auto_shutdown, idle_shutdown_seconds=600
                )
        return V1CloudSpaceInstanceConfig(disable_auto_shutdown=None, idle_shutdown_seconds=600)

    mock_update_sleep_config.side_effect = response

    studio_api = StudioApi()

    config = studio_api.update_autoshutdown(studio_id="st-abc", teamspace_id="ts-abc", enabled=False)
    assert config.disable_auto_shutdown is True
    assert config.idle_shutdown_seconds == 600


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_sleep_config",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_update_autoshutdown_idle_shutdown(mock_update_sleep_config):
    def response(self, id, project_id, body):
        if id == "st-abc":
            if (
                body.disable_auto_shutdown is not None
                and body.idle_shutdown_seconds is not None
                and body.idle_shutdown_seconds > 0
            ):
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=body.disable_auto_shutdown, idle_shutdown_seconds=body.idle_shutdown_seconds
                )

            if body.idle_shutdown_seconds is not None and body.idle_shutdown_seconds > 0:
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=False, idle_shutdown_seconds=body.idle_shutdown_seconds
                )

            if body.disable_auto_shutdown is not None:
                return V1CloudSpaceInstanceConfig(
                    disable_auto_shutdown=body.disable_auto_shutdown, idle_shutdown_seconds=600
                )
        return V1CloudSpaceInstanceConfig(disable_auto_shutdown=None, idle_shutdown_seconds=600)

    mock_update_sleep_config.side_effect = response

    studio_api = StudioApi()

    config = studio_api.update_autoshutdown(studio_id="st-abc", teamspace_id="ts-abc", idle_shutdown_seconds=900)
    assert config.disable_auto_shutdown is False
    assert config.idle_shutdown_seconds == 900


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_env():
    from lightning_sdk.lightning_cloud.openapi import V1EnvVar

    studio_api = StudioApi()

    # Create mock studio with environment variables
    mock_studio = V1CloudSpace(
        id="st-abc",
        name="st-abc",
        env=[
            V1EnvVar(name="TEST_VAR", value="test_value"),
            V1EnvVar(name="ANOTHER_VAR", value="another_value"),
            V1EnvVar(name="EMPTY_VAR", value=""),
        ],
    )

    result = studio_api.get_env(mock_studio)

    expected = {"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value", "EMPTY_VAR": ""}

    assert result == expected


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_env_empty():
    studio_api = StudioApi()

    # Create mock studio with no environment variables
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", env=[])

    result = studio_api.get_env(mock_studio)

    assert result == {}


@mock.patch("lightning_sdk.api.studio_api.StudioApi._update_cloudspace")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_set_env_partial_true(mock_update_cloudspace):
    from lightning_sdk.lightning_cloud.openapi import V1EnvVar

    studio_api = StudioApi()

    # Create mock studio with existing environment variables
    mock_studio = V1CloudSpace(
        id="st-abc",
        name="st-abc",
        env=[V1EnvVar(name="EXISTING_VAR", value="existing_value"), V1EnvVar(name="TO_UPDATE", value="old_value")],
    )

    new_env = {"TO_UPDATE": "new_value", "NEW_VAR": "new_value"}

    studio_api.set_env(mock_studio, "ts-abc", new_env, partial=True)

    # Verify _update_cloudspace was called with correct parameters
    mock_update_cloudspace.assert_called_once()
    call_args = mock_update_cloudspace.call_args

    # Check the arguments: studio, teamspace_id, key, value
    assert call_args[0][0] == mock_studio  # studio
    assert call_args[0][1] == "ts-abc"  # teamspace_id
    assert call_args[0][2] == "env"  # key

    # Check that the env list contains merged environment variables
    env_vars = call_args[0][3]  # value (list of V1EnvVar)
    env_dict = {env.name: env.value for env in env_vars}

    expected_env = {
        "EXISTING_VAR": "existing_value",  # kept from original
        "TO_UPDATE": "new_value",  # updated
        "NEW_VAR": "new_value",  # added
    }

    assert env_dict == expected_env


@mock.patch("lightning_sdk.api.studio_api.StudioApi._update_cloudspace")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_set_env_partial_false(mock_update_cloudspace):
    from lightning_sdk.lightning_cloud.openapi import V1EnvVar

    studio_api = StudioApi()

    # Create mock studio with existing environment variables
    mock_studio = V1CloudSpace(
        id="st-abc",
        name="st-abc",
        env=[V1EnvVar(name="EXISTING_VAR", value="existing_value"), V1EnvVar(name="TO_REMOVE", value="remove_me")],
    )

    new_env = {"ONLY_NEW_VAR": "only_new_value"}

    studio_api.set_env(mock_studio, "ts-abc", new_env, partial=False)

    # Verify _update_cloudspace was called with correct parameters
    mock_update_cloudspace.assert_called_once()
    call_args = mock_update_cloudspace.call_args

    # Check the arguments: studio, teamspace_id, key, value
    assert call_args[0][0] == mock_studio  # studio
    assert call_args[0][1] == "ts-abc"  # teamspace_id
    assert call_args[0][2] == "env"  # key

    # Check that the env list contains only the new environment variables
    env_vars = call_args[0][3]  # value (list of V1EnvVar)
    env_dict = {env.name: env.value for env in env_vars}

    expected_env = {"ONLY_NEW_VAR": "only_new_value"}

    assert env_dict == expected_env


@mock.patch("lightning_sdk.api.studio_api.StudioApi._update_cloudspace")
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_set_env_empty_new_env(mock_update_cloudspace):
    from lightning_sdk.lightning_cloud.openapi import V1EnvVar

    studio_api = StudioApi()

    # Create mock studio with existing environment variables
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", env=[V1EnvVar(name="EXISTING_VAR", value="existing_value")])

    new_env = {}

    # Test partial=True with empty new_env (should keep existing)
    studio_api.set_env(mock_studio, "ts-abc", new_env, partial=True)

    call_args = mock_update_cloudspace.call_args
    env_vars = call_args[0][3]  # value (list of V1EnvVar)
    env_dict = {env.name: env.value for env in env_vars}

    assert env_dict == {"EXISTING_VAR": "existing_value"}

    # Reset mock for second test
    mock_update_cloudspace.reset_mock()

    # Test partial=False with empty new_env (should clear all)
    studio_api.set_env(mock_studio, "ts-abc", new_env, partial=False)

    call_args = mock_update_cloudspace.call_args
    env_vars = call_args[0][3]  # value (list of V1EnvVar)

    assert env_vars == []


@pytest.mark.parametrize(
    ("machine", "accelerators", "expected_result"),
    [
        # GPU, available
        (
            Machine.T4,
            [
                V1ClusterAccelerator(
                    instance_id="g4dn.2xlarge",
                    slug_multi_cloud="lit-t4-1",
                    enabled=True,
                    resources=V1Resources(gpu=1),
                    family="T4",
                    accelerator_type="GPU",
                    out_of_capacity=False,
                )
            ],
            True,
        ),
        # GPU, unavailable
        (
            Machine.T4,
            [
                V1ClusterAccelerator(
                    instance_id="g4dn.2xlarge",
                    slug_multi_cloud="lit-t4-1",
                    enabled=True,
                    resources=V1Resources(gpu=1),
                    family="T4",
                    accelerator_type="GPU",
                    out_of_capacity=True,
                )
            ],
            False,
        ),
        # CPU, available
        (
            Machine.CPU,
            [
                V1ClusterAccelerator(
                    instance_id="cpu-4",
                    slug_multi_cloud="cpu-4",
                    enabled=True,
                    resources=V1Resources(cpu=4),
                    family="CPU",
                    accelerator_type="CPU",
                    out_of_capacity=False,
                )
            ],
            True,
        ),
        # CPU, unavailable
        (
            Machine.CPU,
            [
                V1ClusterAccelerator(
                    instance_id="cpu-4",
                    slug_multi_cloud="cpu-4",
                    enabled=True,
                    resources=V1Resources(cpu=4),
                    family="CPU",
                    accelerator_type="CPU",
                    out_of_capacity=True,
                )
            ],
            False,
        ),
    ],
)
@mock.patch(
    "lightning_sdk.api.studio_api.StudioApi._get_machines_for_cloud_account",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_machine_has_capacity(mock_get_machines, machine, accelerators, expected_result):
    """Test machine_has_capacity method with various scenarios."""
    mock_get_machines.return_value = accelerators

    studio_api = StudioApi()
    result = studio_api.machine_has_capacity(
        machine=machine, teamspace_id="ts-abc", cloud_account_id="cluster-abc", org_id="org-abc"
    )

    assert result == expected_result
    mock_get_machines.assert_called_once_with(
        mock.ANY, teamspace_id="ts-abc", cloud_account_id="cluster-abc", org_id="org-abc"
    )


@pytest.mark.parametrize(
    ("machine", "accelerators", "expected_result"),
    [
        # GPU, machine supported
        (
            Machine.T4,
            [
                V1ClusterAccelerator(
                    instance_id="g4dn.2xlarge",
                    slug_multi_cloud="lit-t4-1",
                    enabled=True,
                    resources=V1Resources(gpu=1),
                    family="T4",
                    accelerator_type="GPU",
                    out_of_capacity=False,
                )
            ],
            True,
        ),
        # GPU, machine not supported (wrong count)
        (
            Machine.T4,
            [
                V1ClusterAccelerator(
                    instance_id="g4dn.12xlarge",
                    slug_multi_cloud="lit-t4-4",
                    enabled=True,
                    resources=V1Resources(gpu=4),
                    family="T4",
                    accelerator_type="GPU",
                    out_of_capacity=False,
                )
            ],
            False,
        ),
        # GPU, machine not supported (wrong family)
        (
            Machine.T4,
            [
                V1ClusterAccelerator(
                    instance_id="g5.xlarge",
                    slug_multi_cloud="lit-a10g-1",
                    enabled=True,
                    resources=V1Resources(gpu=1),
                    family="A10G",
                    accelerator_type="GPU",
                    out_of_capacity=False,
                )
            ],
            False,
        ),
        # CPU, machine supported
        (
            Machine.CPU,
            [
                V1ClusterAccelerator(
                    instance_id="cpu-4",
                    slug_multi_cloud="cpu-4",
                    enabled=True,
                    resources=V1Resources(cpu=4),
                    family="CPU",
                    accelerator_type="CPU",
                    out_of_capacity=False,
                )
            ],
            True,
        ),
        # CPU, machine not supported (wrong cpu count)
        (
            Machine.CPU,
            [
                V1ClusterAccelerator(
                    instance_id="cpu-8",
                    slug_multi_cloud="cpu-8",
                    enabled=True,
                    resources=V1Resources(cpu=8),
                    family="CPU",
                    accelerator_type="CPU",
                    out_of_capacity=False,
                )
            ],
            False,
        ),
        # out_of_capacity but still supported
        (
            Machine.T4,
            [
                V1ClusterAccelerator(
                    instance_id="g4dn.2xlarge",
                    slug_multi_cloud="lit-t4-1",
                    enabled=True,
                    resources=V1Resources(gpu=1),
                    family="T4",
                    accelerator_type="GPU",
                    out_of_capacity=True,  # still supported, just out of capacity
                )
            ],
            True,
        ),
    ],
)
@mock.patch(
    "lightning_sdk.api.studio_api.StudioApi._get_machines_for_cloud_account",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_machine_is_supported(mock_get_machines, machine, accelerators, expected_result):
    """Test machine_is_supported method with various scenarios."""
    mock_get_machines.return_value = accelerators
    studio_api = StudioApi()
    result = studio_api.machine_is_supported(
        machine=machine, teamspace_id="ts-abc", cloud_account_id="cluster-abc", org_id="org-abc"
    )
    assert result == expected_result
    mock_get_machines.assert_called_once_with(
        mock.ANY, teamspace_id="ts-abc", cloud_account_id="cluster-abc", org_id="org-abc"
    )


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_list_endpoints",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_list_ports(mock_list_endpoints):
    """Test list_ports returns endpoints from the Studio."""

    mock_endpoints = [
        V1Endpoint(name="web", ports=[8080], urls=["https://example.com:8080"]),
        V1Endpoint(name="api", ports=[3000], urls=["https://example.com:3000"]),
        V1Endpoint(name=None, ports=[5000], urls=["https://example.com:5000"]),
    ]

    mock_list_endpoints.return_value = V1ListEndpointsResponse(endpoints=mock_endpoints)

    studio_api = StudioApi()
    endpoints = studio_api.list_ports(teamspace_id="ts-abc", studio_id="st-abc")

    assert len(endpoints) == 3
    assert endpoints[0].name == "web"
    assert endpoints[0].ports == [8080]
    assert endpoints[0].urls == ["https://example.com:8080"]
    assert endpoints[1].name == "api"
    assert endpoints[1].ports == [3000]
    assert endpoints[1].urls == ["https://example.com:3000"]
    assert endpoints[2].name is None
    assert endpoints[2].ports == [5000]
    assert endpoints[2].urls == ["https://example.com:5000"]

    mock_list_endpoints.assert_called_once_with(
        mock.ANY,
        project_id="ts-abc",
        cloudspace_id="st-abc",
    )


@pytest.mark.parametrize(
    ("port", "name", "endpoints", "expected_url", "should_raise", "error_match"),
    [
        (
            8080,
            None,
            [
                V1Endpoint(
                    name="endpoint-1",
                    ports=[8000, 8080, 9000],
                    urls=["http://url-8000", "http://url-8080", "http://url-9000"],
                )
            ],
            "http://url-8080",
            False,
            None,
        ),
        (
            None,
            "my-endpoint",
            [
                V1Endpoint(name="other-endpoint", ports=[8000], urls=["http://wrong"]),
                V1Endpoint(name="my-endpoint", ports=[8080], urls=["http://correct"]),
            ],
            "http://correct",
            False,
            None,
        ),
        (
            9999,
            None,
            [V1Endpoint(name="endpoint-1", ports=[8000], urls=["http://localhost:8000"])],
            None,
            True,
            "Endpoint with port 9999 not found",
        ),
        (
            None,
            None,
            [V1Endpoint(name="endpoint-1", ports=[8000], urls=["http://localhost:8000"])],
            None,
            True,
            "Either 'port' or 'name' must be provided",
        ),
        (
            8080,
            None,
            [
                V1Endpoint(name="endpoint-1", ports=[8000], urls=["http://url-1"]),
                V1Endpoint(name="endpoint-2", ports=[8080], urls=["http://url-2"]),
                V1Endpoint(name="endpoint-3", ports=[9000], urls=["http://url-3"]),
            ],
            "http://url-2",
            False,
            None,
        ),
    ],
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_list_endpoints",
    autospec=True,
)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_get_port_url(mock_list_endpoints, port, name, endpoints, expected_url, should_raise, error_match):
    """Test get_port_url with various port and name scenarios."""
    mock_list_endpoints.return_value = V1ListEndpointsResponse(endpoints=endpoints)

    studio_api = StudioApi()

    if should_raise:
        with pytest.raises(ValueError, match=error_match):
            studio_api.get_port_url(teamspace_id="ts-abc", studio_id="st-abc", port=port, name=name)
    else:
        result = studio_api.get_port_url(teamspace_id="ts-abc", studio_id="st-abc", port=port, name=name)
        assert result == expected_url

    if port is not None or name is not None:
        mock_list_endpoints.assert_called_once_with(
            mock.ANY,
            project_id="ts-abc",
            cloudspace_id="st-abc",
        )
    else:
        mock_list_endpoints.assert_not_called()


@pytest.mark.parametrize(
    ("path", "path_info", "status_code", "should_raise", "error_match"),
    [
        (
            "file.txt",
            {"type": "file", "exists": True, "size": 1024},
            204,
            False,
            None,
        ),
        # non-existent file
        (
            "nonexistent.txt",
            {"type": "file", "exists": False, "size": None},
            None,
            True,
            "The path 'nonexistent.txt' does not exist in the Studio.",
        ),
        # directory
        (
            "my-folder",
            {"type": "directory", "exists": True, "size": None},
            None,
            True,
            "The path 'my-folder' is a directory. Use 'remove_folder\\(\\)' to remove directories.",
        ),
        # server error on file
        (
            "file.txt",
            {"type": "file", "exists": True, "size": 1024},
            500,
            True,
            "Failed to remove file 'file.txt' from the Studio. Status code: 500",
        ),
    ],
)
@mock.patch("requests.delete", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="test-token")
@mock.patch("lightning_sdk.api.studio_api.StudioApi.get_path_info", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_remove_file(
    mock_get_path_info,
    mock_authenticate,
    mock_requests_delete,
    path,
    path_info,
    status_code,
    should_raise,
    error_match,
):
    """Test remove_file method with various scenarios."""
    mock_get_path_info.return_value = path_info

    if status_code is not None:
        mock_response = mock.MagicMock()
        mock_response.status_code = status_code
        mock_response.text = "Error response text"
        mock_requests_delete.return_value = mock_response

    studio_api = StudioApi()

    if should_raise:
        with pytest.raises((IsADirectoryError, FileNotFoundError, RuntimeError), match=error_match):
            studio_api.remove_file("st-abc", "ts-abc", path)
    else:
        result = studio_api.remove_file("st-abc", "ts-abc", path)
        # None means success
        assert result is None
        mock_requests_delete.assert_called_once()
        call_args = mock_requests_delete.call_args

        assert f"/v1/projects/ts-abc/artifacts/cloudspaces/st-abc/blobs/{path}" in call_args[0][0]
        assert call_args[1]["params"]["token"] == "test-token"
        assert call_args[1]["timeout"] == 30
        mock_authenticate.assert_called_once_with(studio_api._client)

    mock_get_path_info.assert_called_once_with(mock.ANY, "st-abc", "ts-abc", path=path)


@pytest.mark.parametrize(
    ("path", "path_info", "status_code", "should_raise", "error_match"),
    [
        (
            "my-folder",
            {"type": "directory", "exists": True, "size": None},
            204,
            False,
            None,
        ),
        # non-existent folder
        (
            "nonexistent-folder",
            {"type": "directory", "exists": False, "size": None},
            None,
            True,
            "The path 'nonexistent-folder' does not exist in the Studio.",
        ),
        # path is a file
        (
            "file.txt",
            {"type": "file", "exists": True, "size": 1024},
            None,
            True,
            "The path 'file.txt' is a file. Use 'remove_file\\(\\)' to remove files.",
        ),
        # server error on folder
        (
            "my-folder",
            {"type": "directory", "exists": True, "size": None},
            500,
            True,
            "Failed to remove folder 'my-folder' from the Studio. Status code: 500",
        ),
    ],
)
@mock.patch("requests.delete", autospec=True)
@mock.patch("lightning_sdk.api.studio_api._authenticate_and_get_token", return_value="test-token")
@mock.patch("lightning_sdk.api.studio_api.StudioApi.get_path_info", autospec=True)
@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_remove_folder(
    mock_get_path_info,
    mock_authenticate,
    mock_requests_delete,
    path,
    path_info,
    status_code,
    should_raise,
    error_match,
):
    """Test remove_folder method with various scenarios."""
    mock_get_path_info.return_value = path_info

    if status_code is not None:
        mock_response = mock.MagicMock()
        mock_response.status_code = status_code
        mock_response.text = "Error response text"
        mock_requests_delete.return_value = mock_response

    studio_api = StudioApi()

    if should_raise:
        with pytest.raises((ValueError, FileNotFoundError, RuntimeError), match=error_match):
            studio_api.remove_folder("st-abc", "ts-abc", path)
    else:
        result = studio_api.remove_folder("st-abc", "ts-abc", path)
        # None means success
        assert result is None
        mock_requests_delete.assert_called_once()
        call_args = mock_requests_delete.call_args

        assert f"/v1/projects/ts-abc/artifacts/cloudspaces/st-abc/trees/{path}" in call_args[0][0]
        assert call_args[1]["params"]["token"] == "test-token"
        assert call_args[1]["timeout"] == 30
        mock_authenticate.assert_called_once_with(studio_api._client)

    mock_get_path_info.assert_called_once_with(mock.ANY, "st-abc", "ts-abc", path=path)
