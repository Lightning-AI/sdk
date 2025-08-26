import contextlib
import json
import os
import subprocess
from unittest import mock

import pytest

from lightning_sdk.api import studio_api as studio_api_module
from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.api.utils import _BYTES_PER_MB
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    Externalv1LightningappInstance,
    ProjectIdCloudspacesBody,
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
    V1ListProjectClustersResponse,
    V1LoginResponse,
    V1Organization,
    V1Plugin,
    V1PluginsListResponse,
    V1Project,
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
def test_create_studio(mock_create_cloud_space, mock_create_lightning_run, _, cloud_account, sandbox, disable_secrets):
    def _create_cloudspace_side_effect(self, body, project_id, **kwargs):
        assert isinstance(body, ProjectIdCloudspacesBody)
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


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
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
    studio_api.switch_studio_machine("st-abc", "ts-abc", Machine.A100_X_8, False)


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
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
            spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
        ),
        V1ExternalCluster(
            id="c-abc",
            spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
        ),
        V1ExternalCluster(
            id="cluster-abc",
            spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
        ),
        V1ExternalCluster(
            id="my-preferred-cluster",
            spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
        ),
        V1ExternalCluster(
            id=None,
            spec=V1ExternalClusterSpec(driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL),
        ),
    ]

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=test_cloud_accounts)
    mock_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(instance_id="cpu-4", slug_multi_cloud="cpu-4", enabled=True),
            V1ClusterAccelerator(instance_id="data-large", slug_multi_cloud="data-prep-mid", enabled=True),
            V1ClusterAccelerator(instance_id="g4dn.2xlarge", slug_multi_cloud="lit-t4-1", enabled=True),
            V1ClusterAccelerator(instance_id="g4dn.12xlarge", slug_multi_cloud="lit-t4-4", enabled=True),
            V1ClusterAccelerator(instance_id="g6.4xlarge", slug_multi_cloud="lit-l4-1", enabled=True),
            V1ClusterAccelerator(instance_id="g6.12xlarge", slug_multi_cloud="lit-l4-4", enabled=True),
            V1ClusterAccelerator(instance_id="p4d.24xlarge", slug_multi_cloud="lit-a100-8", enabled=True),
            V1ClusterAccelerator(instance_id="p5.48xlarge", slug_multi_cloud="lit-h100-8", enabled=True),
            V1ClusterAccelerator(instance_id="p5en.48xlarge", slug_multi_cloud="lit-h200x-8", enabled=True),
            V1ClusterAccelerator(instance_id="data-max", slug_multi_cloud="data-prep-max-large", enabled=True),
            V1ClusterAccelerator(
                instance_id="data-ultra", slug_multi_cloud="data-prep-ultra-extra-large", enabled=True
            ),
            V1ClusterAccelerator(instance_id="m3.medium", slug_multi_cloud="cpu-2", enabled=True),
            V1ClusterAccelerator(instance_id="g6e.4xlarge", slug_multi_cloud="lit-l40s-1", enabled=True),
            V1ClusterAccelerator(instance_id="g6e.12xlarge", slug_multi_cloud="lit-l40s-4", enabled=True),
            V1ClusterAccelerator(instance_id="g6e.48xlarge", slug_multi_cloud="lit-l40s-8", enabled=True),
            V1ClusterAccelerator(instance_id="g6.48xlarge", slug_multi_cloud="lit-l4-8", enabled=True),
            V1ClusterAccelerator(instance_id="a2-ultragpu-2g", slug_multi_cloud="lit-a100-2", enabled=True),
            V1ClusterAccelerator(instance_id="a2-ultragpu-4g", slug_multi_cloud="lit-a100-4", enabled=True),
            V1ClusterAccelerator(instance_id="a4-highgpu-8g", slug_multi_cloud="lit-b200x-8", enabled=True),
            V1ClusterAccelerator(instance_id="n2d-standard-2", slug_multi_cloud="cpu-2", enabled=True),
            V1ClusterAccelerator(instance_id="g2-standard-24", slug_multi_cloud="lit-l4-2", enabled=True),
        ]
    )

    studio_api = StudioApi()

    machine = studio_api.get_machine(name, "ts-abc", "cluster-abc", "test-org")

    assert isinstance(machine, Machine)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_install_plugin",
    autospec=True,
)
def test_install_plugin(mock_install_plugin, studio_id, expect_error, error_message, expect_info):
    def _plugin_install_side_effect(self, project_id, id, plugin_id):
        assert plugin_id == "my-fancy-plugin"
        if id == "st-abc":
            return V1Plugin(state="installation_success", error="")
        if id == "st-def":
            return V1Plugin(state="installation_success", error="abc")
        if id == "st-ghi":
            return V1Plugin(state="installation_error", error="")
        if id == "st-jkl":
            return V1Plugin(state="installation_error", error="jkl")
        if id == "st-mno":
            return V1Plugin(state="installation_success", error="", additional_info=" my-info \n")
        return None

    mock_install_plugin.side_effect = _plugin_install_side_effect

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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_uninstall_plugin",
    autospec=True,
)
def test_uninstall_plugin(mock_uninstall_plugin, studio_id, expect_error, error_message):
    def _plugin_uninstall_side_effect(self, project_id, id, plugin_id):
        assert plugin_id == "my-fancy-plugin"
        if id == "st-abc":
            return V1Plugin(state="uninstallation_success", error="")
        if id == "st-def":
            return V1Plugin(state="uninstallation_success", error="abc")
        if id == "st-ghi":
            return V1Plugin(state="uninstallation_error", error="")
        if id == "st-jkl":
            return V1Plugin(state="uninstallation_error", error="jkl")
        return None

    mock_uninstall_plugin.side_effect = _plugin_uninstall_side_effect

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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_plugin",
    autospec=True,
)
def test_execute_plugin(mock_execute_plugin, studio_id, expect_error, error_message, expected_port):
    def _plugin_execute_side_effect(self, project_id, id, plugin_id):
        assert plugin_id == "my-fancy-plugin"
        if id == "st-abc":
            return V1Plugin(state="execution_success", error="", additional_info='{"port": 0}')
        if id == "st-def":
            return V1Plugin(state="execution_success", error="", additional_info='{"port": 1}')
        if id == "st-ghi":
            return V1Plugin(state="execution_success", error="", additional_info='{"port": -1}')
        if id == "st-jkl":
            return V1Plugin(state="execution_success", error="jkl")
        if id == "st-mno":
            return V1Plugin(state="execution_error", error="")
        if id == "st-pqr":
            return V1Plugin(state="execution_error", error="pqr")
        return None

    mock_execute_plugin.side_effect = _plugin_execute_side_effect

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


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
def test_list_available_plugins(mock_list_available_plugins):
    mock_list_available_plugins.return_value = V1PluginsListResponse(
        plugins={"plugin1": "description1", "plugin2": "description2", "plugin3": "description3"}
    )

    studio_api = StudioApi()

    plugins = studio_api.list_available_plugins("st-abc", "teamspace-abc")

    assert plugins == {"plugin1": "description1", "plugin2": "description2", "plugin3": "description3"}


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
def test_list_installed_plugins(mock_list_installed_plugins):
    mock_list_installed_plugins.return_value = V1PluginsListResponse(
        plugins={
            "plugin1": "description1",
            "plugin2": "description2",
        }
    )

    studio_api = StudioApi()

    plugins = studio_api.list_installed_plugins("st-abc", "teamspace-abc")

    assert plugins == {
        "plugin1": "description1",
        "plugin2": "description2",
    }


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
    autospec=True,
)
def test_create_job(mock_create_app):
    def side_effect(self, body, project_id, cloudspace_id, id):
        if id == "job":
            assert body.plugin_arguments == {
                "entrypoint": "my-entry-point",
                "name": "fancy-job-name",
                "compute": "lit-l4-1",
                "spot": "false",
            }

        return V1CreateCloudSpaceAppInstanceResponse(
            lightningappinstance=Externalv1LightningappInstance(name=body.plugin_arguments["name"])
        )

    mock_create_app.side_effect = side_effect

    studio_api = StudioApi()

    resp = studio_api.create_job(
        "my-entry-point", "fancy-job-name", Machine.L4, "st-abc", "ts-abc", "cluster-abc", False
    )
    assert resp.name == "fancy-job-name"


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
    autospec=True,
)
def test_create_mmt(mock_create_app):
    def side_effect(self, body, project_id, cloudspace_id, id):
        if id == "distributed_plugin":
            assert body.plugin_arguments == {
                "entrypoint": "my-entry-point",
                "name": "fancy-mmt-name",
                "distributedArguments": json.dumps(
                    {"cloud_compute": "lit-l4-1", "num_instances": 4, "strategy": "parallel"}
                ),
                "spot": "false",
            }

        return V1CreateCloudSpaceAppInstanceResponse(
            lightningappinstance=Externalv1LightningappInstance(name=body.plugin_arguments["name"])
        )

    mock_create_app.side_effect = side_effect

    studio_api = StudioApi()

    resp = studio_api.create_multi_machine_job(
        "my-entry-point", "fancy-mmt-name", 4, Machine.L4, "parallel", "st-abc", "ts-abc", "cluster-abc", False
    )
    assert resp.name == "fancy-mmt-name"


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


@pytest.mark.parametrize("progress_bar", [True, False])
@mock.patch("lightning_sdk.api.studio_api._FileUploader", autospec=True)
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
    uploader_mock.return_value.assert_called_with()  # .__call__()


@mock.patch("requests.get", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login", autospec=True
)
def test_download_file(mock_login, mock_requests_get, tmpdir):
    mock_login.return_value = V1LoginResponse(token="token")

    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_file("file1", filepath, "st-abc", "ts-abc", "cluster-abc")


@mock.patch("lightning_sdk.api.studio_api._download_teamspace_files", autospec=True)
def test_download_folder(mock_download, tmpdir):
    studio_api = StudioApi()

    filepath = os.path.join(tmpdir, "file1")
    studio_api.download_folder("file1", filepath, "st-abc", "ts-abc", "cluster-abc")
    mock_download.assert_called_once()


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_create_endpoint",
    autospec=True,
)
def test_start_new_port(mock_create_endpoint):
    mock_create_endpoint.return_value = V1Endpoint(
        id="endpoint-id",
        name="endpoint-name",
        urls=["http://localhost:8000"],
    )

    studio_api = StudioApi()

    url = studio_api.start_new_port("st-abc", "ts-abc", "test", 8000)

    assert url == "http://localhost:8000", "endpoint_service_create_endpoint returns [localhost:8000] for urls"


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_sleep_config",
    autospec=True,
)
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


def test_get_env_empty():
    studio_api = StudioApi()

    # Create mock studio with no environment variables
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", env=[])

    result = studio_api.get_env(mock_studio)

    assert result == {}


@mock.patch("lightning_sdk.api.studio_api.StudioApi._update_cloudspace")
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
