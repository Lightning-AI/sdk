import os
from unittest import mock

from lightning_sdk.lightning_cloud.openapi import (
    CloudSpaceServiceCreateCloudSpaceBody,
    CloudSpaceServiceStartCloudSpaceInstanceBody,
    Externalv1CloudSpaceInstanceStatus,
    V1AWSDirectV1,
    V1CloudProvider,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceInstanceStartupStatus,
    V1ClusterAccelerator,
    V1ClusterType,
    V1ExternalCluster,
    V1ExternalClusterSpec,
    V1GetCloudSpaceInstanceStatusResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListClustersResponse,
    V1ListDefaultClusterAcceleratorsResponse,
    V1ListProjectClustersResponse,
    V1Organization,
    V1PluginsListResponse,
    V1Project,
    V1ProjectSettings,
    V1Resources,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.machine import Machine
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio


def list_cloudspaces_side_effect(existing_studios):
    def _list_cloudspaces_side_effect(*args, **kwargs):
        name = kwargs.get("name")
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    return _list_cloudspaces_side_effect


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

    def _create_cloudspace_side_effect(body, project_id, **kwargs):
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
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
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
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
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
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

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
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
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
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
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
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

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
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
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
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
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
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

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
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
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
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
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_create_lightning_run.return_value = V1PluginsListResponse(plugins={})
    mock_create_cloudspace.return_value = V1PluginsListResponse(plugins={})

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped
    assert studio.machine is None

    studio.start(machine="T4")

    mock_start_instance.assert_called_once_with(
        mock.ANY,
        CloudSpaceServiceStartCloudSpaceInstanceBody(
            compute_config=V1UserRequestedComputeConfig(
                name="lit-t4-1",  # should be able to convert string "T4" to "lit-t4-1"
                spot=True,
            )
        ),
        "ts-abc",
        "st-abc",
    )


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_SPACE_ID": "st-current"}, clear=False)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start_uses_current_studio_machine_when_inside_running_studio(
    mock_get_teamspace,
    mock_get_org,
    mock_get_cloud_space,
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
    """Test that when starting a studio from inside a running studio, it uses the current studio's machine."""
    status = {"st-abc": None, "st-current": "CLOUD_SPACE_INSTANCE_STATE_RUNNING"}
    machines = {"st-abc": None, "st-current": V1UserRequestedComputeConfig(name="gpu-rtx-1", spot=False)}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        id_arg = args[3] if len(args) > 3 else kwargs.get("id")
        status[id_arg] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines[id_arg] = V1UserRequestedComputeConfig(name=body.compute_config.name, spot=body.compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status.get(id),
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1CloudSpaceInstanceConfig(compute_config=machines.get(id))

    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc",
            display_name="st-abc",
            cluster_id="c-abc",
            project_id="ts-abc",
            id="st-abc",
            code_status=V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=None)),
        ),
        "st-current": V1CloudSpace(
            name="st-current",
            display_name="st-current",
            cluster_id="c-abc",
            project_id="ts-abc",
            id="st-current",
            code_status=V1GetCloudSpaceInstanceStatusResponse(
                in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
            ),
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
            code_status=V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=None)),
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _create_lightning_run_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        cloudspace_id = args[3] if len(args) > 3 else kwargs.get("cloudspace_id")
        return V1LightningRun(
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    def _get_cloud_space_side_effect(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return existing_studios.get(id)

    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
    ]

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
                accelerator_type="GPU",
                instance_id="g5.xlarge",
                slug_multi_cloud="gpu-rtx-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="RTX_4000",
            ),
        ]
    )
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_cloud_space.side_effect = _get_cloud_space_side_effect

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(start_studio_on_spot_instance=False),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped

    studio.start()

    assert studio.status == Status.Running
    assert machines["st-abc"].name == "g5.xlarge"


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_SPACE_ID": "st-current"}, clear=False)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start_ignores_stopped_current_studio_machine(
    mock_get_teamspace,
    mock_get_org,
    mock_get_cloud_space,
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
    """Test that when inside stopped studio, start() uses the default machine instead of current studio machine."""
    status = {"st-abc": None, "st-current": None}
    machines = {"st-abc": None, "st-current": V1UserRequestedComputeConfig(name="gpu-rtx-1", spot=False)}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        id_arg = args[3] if len(args) > 3 else kwargs.get("id")
        status[id_arg] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines[id_arg] = V1UserRequestedComputeConfig(name=body.compute_config.name, spot=body.compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status.get(id),
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1CloudSpaceInstanceConfig(compute_config=machines.get(id))

    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-current": V1CloudSpace(
            name="st-current", display_name="st-current", cluster_id="c-abc", project_id="ts-abc", id="st-current"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
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
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    def _get_cloud_space_side_effect(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return existing_studios.get(id)

    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
    ]

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
        ]
    )
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_cloud_space.side_effect = _get_cloud_space_side_effect

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(start_studio_on_spot_instance=False),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped

    studio.start()

    assert studio.status == Status.Running
    assert studio.machine == Machine.CPU


@mock.patch.dict(os.environ, {"LIGHTNING_CLOUD_SPACE_ID": "st-current"}, clear=False)
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
@mock.patch(
    "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
    autospec=True,
)
@mock.patch("lightning_sdk.api.org_api.OrgApi.get_org", autospec=True)
@mock.patch("lightning_sdk.api.teamspace_api.TeamspaceApi.get_teamspace", autospec=True)
def test_studio_start_explicit_machine_overrides_current_studio_machine(
    mock_get_teamspace,
    mock_get_org,
    mock_get_cloud_space,
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
    """Test that explicitly specifying a machine overrides the current studio's machine."""
    status = {"st-abc": None, "st-current": "CLOUD_SPACE_INSTANCE_STATE_RUNNING"}
    machines = {"st-abc": None, "st-current": V1UserRequestedComputeConfig(name="gpu-rtx-1", spot=False)}

    def side_effect_start(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        id_arg = args[3] if len(args) > 3 else kwargs.get("id")
        status[id_arg] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        machines[id_arg] = V1UserRequestedComputeConfig(name=body.compute_config.name, spot=body.compute_config.spot)
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status.get(id),
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_get_cloud_space_instance_config(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return V1CloudSpaceInstanceConfig(compute_config=machines.get(id))

    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-current": V1CloudSpace(
            name="st-current", display_name="st-current", cluster_id="c-abc", project_id="ts-abc", id="st-current"
        ),
    }

    def _create_cloudspace_side_effect(*args, **kwargs):
        body = args[1] if len(args) > 1 else kwargs.get("body")
        project_id = args[2] if len(args) > 2 else kwargs.get("project_id")
        assert isinstance(body, CloudSpaceServiceCreateCloudSpaceBody)
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
            cluster_id=body.cluster_id,
            cloudspace_id=cloudspace_id,
            project_id=project_id,
            id=cloudspace_id + "_run",
        )

    def _get_cloud_space_side_effect(*args, **kwargs):
        id = kwargs.get("id") or (args[2] if len(args) > 2 else None)
        return existing_studios.get(id)

    test_cloud_accounts = [
        V1ExternalCluster(
            id="c-abc",
            spec=V1ExternalClusterSpec(
                driver=V1CloudProvider.AWS, cluster_type=V1ClusterType.GLOBAL, aws_v1=V1AWSDirectV1()
            ),
        ),
    ]

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
                instance_id="cpu-medium",
                slug_multi_cloud="cpu-8",
                enabled=True,
                resources=V1Resources(cpu=8),
                family="CPU",
            ),
            V1ClusterAccelerator(
                accelerator_type="GPU",
                instance_id="g5.xlarge",
                slug_multi_cloud="gpu-rtx-1",
                enabled=True,
                resources=V1Resources(gpu=1),
                family="RTX_4000",
            ),
        ]
    )
    mock_list_cloudspaces.side_effect = list_cloudspaces_side_effect(existing_studios)
    mock_create_cloudspace.side_effect = _create_cloudspace_side_effect
    mock_create_lightning_run.side_effect = _create_lightning_run_side_effect
    mock_get_cloud_space.side_effect = _get_cloud_space_side_effect

    mock_get_teamspace.return_value = V1Project(
        name="ts-abc",
        display_name="ts-abc",
        id="ts-abc",
        project_settings=V1ProjectSettings(start_studio_on_spot_instance=False),
    )
    mock_get_org.return_value = V1Organization(
        display_name="org-abc", name="org-abc", id="org-abc", preferred_cluster="c-abc"
    )

    studio = Studio(name="st-abc", teamspace="ts-abc", org="org-abc")
    assert studio.status == Status.Stopped

    studio.start(machine="cpu-8")

    assert studio.status == Status.Running
    assert studio.machine == Machine.from_str("cpu-8")
