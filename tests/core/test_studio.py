import os
import time
from contextlib import nullcontext
from unittest import mock

import pytest

from lightning_sdk.api.studio_api import StudioApi
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    ProjectIdCloudspacesBody,
    V1AWSDirectV1,
    V1CloudProvider,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceInstanceStartupStatus,
    V1ClusterAccelerator,
    V1ClusterType,
    V1ExecuteCloudSpaceCommandResponse,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GoogleCloudDirectV1,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListClustersResponse,
    V1ListDefaultClusterAcceleratorsResponse,
    V1ListProjectClustersResponse,
    V1Organization,
    V1Plugin,
    V1PluginsListResponse,
    V1Project,
    V1ProjectSettings,
    V1Resources,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.machine import CloudProvider, Machine
from lightning_sdk.plugin import (
    Plugin,
)
from lightning_sdk.status import Status
from lightning_sdk.studio import VM, Studio


class _DummyResponse:
    data: bytes


@pytest.mark.parametrize("create_ok", [True, False])
@pytest.mark.parametrize("cluster", [None, "c-abc"])
@pytest.mark.parametrize("name", ["st-abc", "st-xyz"])
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_init(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    name,
    cluster,
    create_ok,
):
    # Setup mocks
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    def _get_status_side_effect(*args, **kwargs):
        id = kwargs.get("id")
        if id == "st-abc":
            status = "CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED"
        elif id == "st-def":
            status = "CLOUD_SPACE_INSTANCE_STATE_PENDING"
        else:
            status = None
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=status))

    # Setup teamspace mock
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    # Setup organization mock
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    # Setup plugin mocks
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    # Setup cloud space service mocks
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_status.side_effect = _get_status_side_effect

    # st-xyz does not exist and should not be created
    error_out = bool(name == "st-xyz" and not create_ok)
    contextman = pytest.raises(ValueError, match="Studio st-xyz does not exist") if error_out else nullcontext()

    with contextman:
        studio = Studio(
            name=name,
            teamspace="ts-abc",
            org="org-abc",
            cloud_account=cluster,
            create_ok=create_ok,
        )

    if error_out:
        return

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"
    assert studio.name == name


@mock.patch.dict(os.environ, {"LIGHTNING_TEAMSPACE": ""}, clear=False)
@mock.patch("lightning_sdk.utils.config.Config.get_value")
@mock.patch("lightning_sdk.studio._resolve_teamspace")
def test_studio_init_no_teamspace(mock_resolve_teamspace, mock_config_get_value):
    # Mock config to return None for teamspace_name
    mock_config_get_value.return_value = None
    # Mock _resolve_teamspace to return None, which should trigger the ValueError
    mock_resolve_teamspace.return_value = None

    with pytest.raises(ValueError, match="Couldn't resolve teamspace from the provided name, org, or user"):
        Studio(
            name="st-xyz",
        )


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
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_status(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    name,
    expected_status,
):
    # Setup status side effect based on fixture logic
    def _get_status_side_effect(self, project_id: str, id: str):
        if id == "st-abc":
            status = "CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED"
        elif id == "st-def":
            status = "CLOUD_SPACE_INSTANCE_STATE_PENDING"
        elif id == "st-ghi":
            status = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        elif id == "st-jkl":
            status = "CLOUD_SPACE_INSTANCE_STATE_FAILED"
        elif id == "st-mno":
            status = "CLOUD_SPACE_INSTANCE_STATE_STOPPING"
        elif id == "st-pqr":
            status = "CLOUD_SPACE_INSTANCE_STATE_STOPPED"
        elif id == "st-stu" or id == "st-xyz":
            status = None
        else:
            raise ValueError(f"Invalid {id=}")
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=status))

    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.side_effect = _get_status_side_effect
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(name=name, teamspace="ts-abc", org="org-abc", create_ok=True)
    assert studio.status == expected_status


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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start(
    mock_get_teamspace,
    mock_get_org,
    mock_get_config,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    mock_start_instance,
    mock_list_project_clusters,
    mock_list_clusters,
    mock_list_accelerators,
):
    # Setup state from internal_studio_start_mocker
    status = {"st-abc": None}
    machines = {"st-abc": None}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines["st-abc"] = V1UserRequestedComputeConfig(name="cpu-4", spot=body._compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id")
        return V1CloudSpaceInstanceConfig(compute_config=machines[id])

    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(body, project_id, **kwargs):
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(body, project_id, cloudspace_id, **kwargs):
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Create test cloud accounts for different cluster_ids used in tests
    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
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
    ]

    # Setup mocks
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_config.side_effect = side_effect_get_cloud_space_instance_config
    mock_get_status.side_effect = side_effect_status
    mock_start_instance.side_effect = side_effect_start
    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=test_cloud_accounts)
    mock_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="cpu-4",
                slug_multi_cloud="cpu-4",
                enabled=True,
                resources=V1Resources(cpu=4),
                family="CPU",
            ),
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="data-large",
                slug_multi_cloud="data-prep-mid",
                enabled=True,
                resources=V1Resources(cpu=32),
                family="DATA_PREP",
            ),
            V1ClusterAccelerator(
                accelerator_type="GPU",
                instance_id="g4dn.2xlarge",
                slug_multi_cloud="lit-t4-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="T4",
            ),
        ]
    )
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    # Setup teamspace and org mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None
    assert studio.teamspace.start_studios_on_interruptible is True

    studio.start()

    assert studio.status == Status.Running
    assert studio.interruptible is True
    assert studio.machine is not None


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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start_on_demand_machine(
    mock_get_teamspace,
    mock_get_org,
    mock_get_config,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    mock_start_instance,
    mock_list_project_clusters,
    mock_list_clusters,
    mock_list_accelerators,
):
    # Setup state from internal_studio_start_mocker
    status = {"st-abc": None}
    machines = {"st-abc": None}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines["st-abc"] = V1UserRequestedComputeConfig(name="cpu-4", spot=body._compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1CloudSpaceInstanceConfig(compute_config=machines[id])

    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Create test cloud accounts for different cluster_ids used in tests
    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
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
    ]

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_config.side_effect = side_effect_get_cloud_space_instance_config
    mock_get_status.side_effect = side_effect_status
    mock_start_instance.side_effect = side_effect_start
    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=test_cloud_accounts)
    mock_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="cpu-4",
                slug_multi_cloud="cpu-4",
                enabled=True,
                resources=V1Resources(cpu=4),
                family="CPU",
            ),
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="data-large",
                slug_multi_cloud="data-prep-mid",
                enabled=True,
                resources=V1Resources(cpu=32),
                family="DATA_PREP",
            ),
            V1ClusterAccelerator(
                accelerator_type="GPU",
                instance_id="g4dn.2xlarge",
                slug_multi_cloud="lit-t4-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="T4",
            ),
        ]
    )
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None
    assert studio.teamspace.start_studios_on_interruptible is True

    studio.start(interruptible=False)

    assert studio.status == Status.Running
    assert studio.machine is not None
    assert studio.interruptible is False


@mock.patch.dict(os.environ, {"LIGHTNING_INTERRUPTIBLE_OVERRIDE": "false"})
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start_interruptible_override(
    mock_get_teamspace,
    mock_get_org,
    mock_get_config,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    mock_start_instance,
    mock_list_project_clusters,
    mock_list_clusters,
    mock_list_accelerators,
):
    # Setup state from internal_studio_start_mocker
    status = {"st-abc": None}
    machines = {"st-abc": None}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines["st-abc"] = V1UserRequestedComputeConfig(name="cpu-4", spot=body.compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1CloudSpaceInstanceConfig(compute_config=machines[id])

    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Create test cloud accounts for different cluster_ids used in tests
    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
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
    ]

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_config.side_effect = side_effect_get_cloud_space_instance_config
    mock_get_status.side_effect = side_effect_status
    mock_start_instance.side_effect = side_effect_start
    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=test_cloud_accounts)
    mock_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="cpu-4",
                slug_multi_cloud="cpu-4",
                enabled=True,
                resources=V1Resources(cpu=4),
                family="CPU",
            ),
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="data-large",
                slug_multi_cloud="data-prep-mid",
                enabled=True,
                resources=V1Resources(cpu=32),
                family="DATA_PREP",
            ),
            V1ClusterAccelerator(
                accelerator_type="GPU",
                instance_id="g4dn.2xlarge",
                slug_multi_cloud="lit-t4-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="T4",
            ),
        ]
    )
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None
    assert studio.teamspace.start_studios_on_interruptible is True

    studio.start()

    assert studio.status == Status.Running
    assert studio.machine is not None
    assert studio.interruptible is False


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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start_different_machine(
    mock_get_teamspace,
    mock_get_org,
    mock_get_config,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
    mock_start_instance,
    mock_list_project_clusters,
    mock_list_clusters,
    mock_list_accelerators,
):
    # Setup state from internal_studio_start_mocker
    status = {"st-abc": None}
    machines = {"st-abc": None}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines["st-abc"] = V1UserRequestedComputeConfig(name="cpu-4", spot=body.compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1CloudSpaceInstanceConfig(compute_config=machines[id])

    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Create test cloud accounts for different cluster_ids used in tests
    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
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
    ]

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_config.side_effect = side_effect_get_cloud_space_instance_config
    mock_get_status.side_effect = side_effect_status
    mock_start_instance.side_effect = side_effect_start
    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(clusters=test_cloud_accounts)
    mock_list_clusters.return_value = V1ListClustersResponse(clusters=[])
    mock_list_accelerators.return_value = V1ListDefaultClusterAcceleratorsResponse(
        accelerator=[
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="cpu-4",
                slug_multi_cloud="cpu-4",
                enabled=True,
                resources=V1Resources(cpu=4),
                family="CPU",
            ),
            V1ClusterAccelerator(
                accelerator_type="CPU",
                instance_id="data-large",
                slug_multi_cloud="data-prep-mid",
                enabled=True,
                resources=V1Resources(cpu=32),
                family="DATA_PREP",
            ),
            V1ClusterAccelerator(
                accelerator_type="GPU",
                instance_id="g4dn.2xlarge",
                slug_multi_cloud="lit-t4-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="T4",
            ),
        ]
    )
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None

    studio.start(Machine.T4)

    assert studio.status == Status.Running
    assert studio.machine is not None


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_run_command(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted")

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio("st-abc", "ts-abc", "org-abc")

    result = studio.run("foo", "bar")

    assert result == "foo-response bar-response"


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_run_command_error(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Submitted Successfully")

    resp = _DummyResponse
    resp.data = b'{"result":{"output":" No such file or directory foo ","exitCode":1}}\n'
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio("st-abc", "ts-abc", "org-abc")

    with pytest.raises(RuntimeError, match="No such file or directory foo"):
        studio.run("foo", "bar")


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_run_command_exit_code(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted")

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio("st-abc", "ts-abc", "org-abc")

    result_output, result_exit_code = studio.run_with_exit_code("foo", "bar")

    assert result_output == "foo-response bar-response"
    assert result_exit_code == 0


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_run_command_and_detach(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_execute_command,
    mock_get_stream,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks (from internal_studio_init_mocker)
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_command.return_value = V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted")

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )
    mock_get_stream.return_value = resp

    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    with mock.patch(
        "lightning_sdk.api.studio_api.StudioApi._get_detached_command_status"
    ) as mock_get_detached_command_status:

        def side_effect(studio_id, teamspace_id, session_id):
            time.sleep(1)
            yield

        mock_get_detached_command_status.side_effect = side_effect
        api = StudioApi()
        # should return immediately
        iterator = api.run_studio_commands_and_yield("st-abc", "ts-abc", "foo", timeout=0, check_interval=0)
        with pytest.raises(StopIteration):
            next(iterator)


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_duplicate_machine(
    mock_get_teamspace,
    mock_get_org,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup studio initialization mocks
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc", start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    studio._studio_api = mock.MagicMock()
    studio._studio_api.duplicate_studio.return_value = {
        "name": "st-abc",
        "teamspace": "ts-abc",
        "org": "org-abc",
    }

    studio.duplicate(machine=Machine.A100)
    studio._studio_api.duplicate_studio.assert_called_once_with(
        studio_id="st-abc",
        teamspace_id="ts-abc",
        target_teamspace_id="ts-abc",
        machine=Machine.A100,
    )


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_plugin",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_run_plugin(
    mock_get_teamspace,
    mock_get_org,
    mock_requests_put,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_get_status,
    mock_execute_plugin,
):
    # Setup studio initialization mocks
    existing_studios = {
        "st-ghi": V1CloudSpace(
            name="st-ghi", display_name="st-ghi", cluster_id="c-abc", project_id="ts-abc", id="st-ghi"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(
            preferred_cluster="my-preferred-cluster", start_studio_on_spot_instance=True
        ),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
        )
    )
    mock_execute_plugin.return_value = V1Plugin(state="execution_success", error="", additional_info='{"port": 0}')

    studio = Studio("st-ghi", "ts-abc", "org-abc")
    studio._plugins = {
        "my-fancy-dummy-plugin": Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)
    }

    studio.run_plugin("my-fancy-dummy-plugin")


@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_install_plugin",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch("requests.put", autospec=True)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_install_plugin(
    mock_get_teamspace,
    mock_get_org,
    mock_requests_put,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_get_status,
    mock_install_plugin,
):
    # Setup studio initialization mocks
    existing_studios = {
        "st-ghi": V1CloudSpace(
            name="st-ghi", display_name="st-ghi", cluster_id="c-abc", project_id="ts-abc", id="st-ghi"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    # Setup mocks
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="c-abc", start_studio_on_spot_instance=True),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_list_available_plugins.return_value = V1PluginsListResponse(
        plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"}
    )
    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(
            phase="CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED",
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=False, top_up_restore_finished=False
            ),
        )
    )

    # Setup plugin installation side effects
    return_value = V1PluginsListResponse(plugins={})

    def _side_effect_list(*args, **kwargs):
        return return_value

    def _side_effect_install(self, project_id, id, plugin_id):
        nonlocal return_value
        assert plugin_id == "my-fancy-dummy-plugin"
        return_value = V1PluginsListResponse(plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"})
        return V1Plugin(state="installation_success", error="")

    mock_list_installed_plugins.side_effect = _side_effect_list
    mock_install_plugin.side_effect = _side_effect_install

    studio = Studio("st-ghi", "ts-abc", "org-abc")
    assert not studio.installed_plugins

    studio.install_plugin("my-fancy-dummy-plugin")
    assert studio.installed_plugins == {
        "my-fancy-dummy-plugin": Plugin("my-fancy-dummy-plugin", "Description of my fancy dummy plugin", studio)
    }


def test_studio_env_property():
    """Test that Studio.env property calls StudioApi.get_env correctly."""
    from lightning_sdk.lightning_cloud.openapi import V1EnvVar

    # Create a simple mock studio object
    mock_studio = V1CloudSpace(
        id="st-abc",
        name="st-abc",
        cluster_id="c-abc",
        env=[V1EnvVar(name="TEST_VAR", value="test_value"), V1EnvVar(name="ANOTHER_VAR", value="another_value")],
    )

    # Mock the Studio object and directly test the env property
    studio = Studio.__new__(Studio)  # Create without __init__
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._studio_api.get_env.return_value = {"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}
    studio._update_studio_reference = mock.MagicMock()

    # Test the env property
    env_vars = studio.env

    assert env_vars == {"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}
    studio._update_studio_reference.assert_called_once()
    studio._studio_api.get_env.assert_called_once_with(mock_studio)


def test_studio_set_env_partial_true():
    """Test that Studio.set_env calls StudioApi.set_env correctly with partial=True."""
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")

    # Mock the Studio object and directly test the set_env method
    studio = Studio.__new__(Studio)  # Create without __init__
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock()
    studio._teamspace.id = "ts-abc"

    new_env = {"NEW_VAR": "new_value", "UPDATED_VAR": "updated_value"}
    studio.set_env(new_env, partial=True)

    studio._studio_api.set_env.assert_called_once_with(mock_studio, "ts-abc", new_env, partial=True)


def test_studio_set_env_partial_false():
    """Test that Studio.set_env calls StudioApi.set_env correctly with partial=False."""
    mock_studio = V1CloudSpace(id="st-abc", name="st-abc", cluster_id="c-abc")

    # Mock the Studio object and directly test the set_env method
    studio = Studio.__new__(Studio)  # Create without __init__
    studio._studio = mock_studio
    studio._studio_api = mock.MagicMock()
    studio._teamspace = mock.MagicMock()
    studio._teamspace.id = "ts-abc"

    new_env = {"ONLY_VAR": "only_value"}
    studio.set_env(new_env, partial=False)

    studio._studio_api.set_env.assert_called_once_with(mock_studio, "ts-abc", new_env, partial=False)


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
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
def test_studio_switch_cloud_account(
    mock_switch_cloudspace_instance,
    mock_update_cloudspace_instance_config,
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    mock_list_clusters.return_value = V1ListClustersResponse(
        [
            V1ExternalCluster(
                id="aws-public", spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.GLOBAL)
            ),
            V1ExternalCluster(
                id="gcp-public",
                spec=V1ExternalClusterSpec(google_cloud_v1=V1GoogleCloudDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
        ]
    )

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse([])

    cloudspace = V1CloudSpace(
        name="st-abc", display_name="st-abc", cluster_id="aws-public", project_id="ts-abc", id="st-abc"
    )

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([cloudspace])

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
    )

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    # Setup plugin mocks
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    assert studio.cloud_account == "aws-public"

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
        ),
    )

    studio.switch_machine(Machine.T4, cloud_provider=CloudProvider.GCP)

    assert studio.cloud_account == "gcp-public"


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_clusters",
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
def test_studio_switch_cloud_account_not_global(
    mock_switch_cloudspace_instance,
    mock_update_cloudspace_instance_config,
    mock_list_clusters,
    mock_list_project_clusters,
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    mock_list_clusters.return_value = V1ListClustersResponse(
        [
            V1ExternalCluster(
                id="aws-public", spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.GLOBAL)
            ),
            V1ExternalCluster(
                id="gcp-public",
                spec=V1ExternalClusterSpec(google_cloud_v1=V1GoogleCloudDirectV1(), cluster_type=V1ClusterType.GLOBAL),
            ),
        ]
    )

    mock_list_project_clusters.return_value = V1ListProjectClustersResponse(
        [
            V1ExternalCluster(
                id="aws-private", spec=V1ExternalClusterSpec(aws_v1=V1AWSDirectV1(), cluster_type=V1ClusterType.BYOC)
            ),
        ]
    )

    cloudspace = V1CloudSpace(
        name="st-abc", display_name="st-abc", cluster_id="aws-private", project_id="ts-abc", id="st-abc"
    )

    mock_list_cloudspaces.return_value = V1ListCloudSpacesResponse([cloudspace])

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
    )

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    # Setup plugin mocks
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
    )

    assert studio.cloud_account == "aws-private"

    assert studio.teamspace.name == "ts-abc"
    assert studio.owner.name == "org-abc"

    mock_get_status.return_value = V1GetCloudSpaceInstanceStatusResponse(
        requested=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            )
        ),
        in_use=Externalv1CloudSpaceInstanceStatus(
            startup_status=V1CloudSpaceInstanceStartupStatus(
                initial_restore_finished=True, top_up_restore_finished=True
            ),
            phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
        ),
    )

    studio.switch_machine(Machine.T4, cloud_provider=CloudProvider.GCP)

    assert studio.cloud_account == "aws-private"


@mock.patch("requests.put", autospec=True)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
    autospec=True,
)
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_vm_cls_name(
    mock_get_teamspace,
    mock_get_org,
    mock_get_status,
    mock_list_cloudspaces,
    mock_create_cloudspace,
    mock_create_lightning_run,
    mock_list_installed_plugins,
    mock_list_available_plugins,
    mock_requests_put,
):
    # Setup mocks
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    def _get_status_side_effect(*args, **kwargs):
        id = kwargs.get("id")
        if id == "st-abc":
            status = "CLOUD_SPACE_INSTANCE_STATE_UNSPECIFIED"
        elif id == "st-def":
            status = "CLOUD_SPACE_INSTANCE_STATE_PENDING"
        else:
            status = None
        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=status))

    # Setup teamspace mock
    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(preferred_cluster="my-preferred-cluster"),
    )

    # Setup organization mock
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="my-preferred-cluster"
    )

    # Setup plugin mocks
    mock_list_available_plugins.return_value = V1PluginsListResponse(plugins={})
    mock_list_installed_plugins.return_value = V1PluginsListResponse(plugins={})

    # Setup cloud space service mocks
    mock_list_cloudspaces.side_effect = _list_cloudspaces_side_effect
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_status.side_effect = _get_status_side_effect

    studio = Studio(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
        cloud_account=None,
    )

    assert studio._cls_name == "Studio"

    vm = VM(
        name="st-abc",
        teamspace="ts-abc",
        org="org-abc",
        cloud_account=None,
    )

    assert vm._cls_name == "VM"
