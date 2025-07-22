import json
import os
import time
from unittest import mock

import pytest
from exceptiongroup import suppress

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    Externalv1Cluster,
    Externalv1LightningappInstance,
    Externalv1Lightningwork,
    IdCodeconfigBody,
    ProjectIdCloudspacesBody,
    ProjectIdMultimachinejobsBody,
    V1Assistant,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1CloudSpaceInstanceStartupStatus,
    V1CloudSpaceState,
    V1ClusterSpec,
    V1ClusterState,
    V1ClusterStatus,
    V1CreateCloudSpaceAppInstanceResponse,
    V1DeleteCloudSpaceResponse,
    V1DownloadJobLogsResponse,
    V1DownloadLightningappInstanceLogsResponse,
    V1Endpoint,
    V1ExecuteCloudSpaceCommandResponse,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetUserResponse,
    V1Job,
    V1JobSpec,
    V1LightningappInstanceSpec,
    V1LightningappInstanceState,
    V1LightningappInstanceStatus,
    V1LightningRun,
    V1LightningworkSpec,
    V1LightningworkState,
    V1LightningworkStatus,
    V1ListCloudSpacesResponse,
    V1ListLightningworkResponse,
    V1ListMembershipsResponse,
    V1ListOrganizationsResponse,
    V1ListProjectClusterBindingsResponse,
    V1ListProjectClustersResponse,
    V1LoginResponse,
    V1Membership,
    V1MultiMachineJob,
    V1Organization,
    V1Plugin,
    V1PluginsListResponse,
    V1Project,
    V1ProjectClusterBinding,
    V1ProjectSettings,
    V1SearchUser,
    V1SearchUsersResponse,
    V1SLURMJob,
    V1UpstreamOpenAI,
    V1UserRequestedComputeConfig,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_create_managed_endpoint_response import (
    V1CreateManagedEndpointResponse,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_managed_endpoint import V1ManagedEndpoint
from lightning_sdk.lightning_cloud.openapi.rest import ApiException

_BEGIN_OUTPUT_TOKEN = "LIGHTNING_BEGIN_OUTPUT"
_END_OUTPUT_TOKEN = "LIGHTNING_END_OUTPUT"


class _DummyResponse:
    data: bytes


@pytest.fixture()
def internal_user_api_mocker(mocker, internal_auth_mocker):
    def side_effect(self, **kwargs):
        if kwargs["query"] == "xyz":
            return V1SearchUsersResponse(users=[])
        return V1SearchUsersResponse(
            users=[
                V1SearchUser(username=kwargs["query"], id=kwargs["query"]),
                V1SearchUser(username=f"{kwargs['query']}-de", id=f"{kwargs['query']}-de"),
            ]
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.user_service_api.UserServiceApi.user_service_search_users",
        side_effect=side_effect,
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_get_user",
        return_value=V1GetUserResponse(id="user-abc", username="user-abc"),
        autospec=True,
    )

    yield [mocker, internal_auth_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_auth_mocker(mocker):
    mocker.patch("lightning_sdk.lightning_cloud.login.Auth.authenticate", autospec=True, return_value="my-auth-header")
    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def internal_list_org_api_mocker(mocker):
    def _side_effect_api_call(
        resource_path,
        method,
        path_params=None,
        query_params=None,
        header_params=None,
        body=None,
        post_params=None,
        files=None,
        response_type=None,
        auth_settings=None,
        async_req=None,
        _return_http_data_only=None,
        collection_formats=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        if response_type == "V1ListOrganizationsResponse":
            return V1ListOrganizationsResponse(
                [
                    V1Organization(display_name="org-abc", name="org-abc"),
                    V1Organization(display_name="org-def", name="org-def"),
                ]
            )
        return None

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api_client.ApiClient.call_api", side_effect=_side_effect_api_call
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_get_org_api_mocker(mocker, internal_auth_mocker):
    def side_effect(self, **kwargs):
        _id, _name = kwargs.get("id", ""), kwargs.get("name", "")

        if not _id:
            _id = _name

        if not _name:
            _name = _id

        assert _id
        assert _name

        if _name == "xyx" or _id == "xyz":
            return None

        return V1Organization(display_name=_name, name=_name, id=_id, preferred_cluster="my-preferred-cluster")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
        side_effect=side_effect,
        autospec=True,
    )
    yield [mocker, internal_auth_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_teamspace_api_mocker(mocker):
    projects = {
        "ts-abc001": V1Membership(
            name="ts-abc", display_name="ts-abc", project_id="ts-abc001", owner_id="org-abc", owner_type="organization"
        ),
        "ts-def001": V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-abc", owner_type="organization"
        ),
        "ts-ghi001": V1Membership(
            name="ts-ghi", display_name="ts-ghi", project_id="ts-ghi001", owner_id="user-abc", owner_type="user"
        ),
        "ts-001": V1Membership(
            name="ts-ghi", display_name="ts-ghi", project_id="ts-ghi001", owner_id="user-abc", owner_type="user"
        ),
    }
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_memberships",
        return_value=V1ListMembershipsResponse(list(projects.values())),
        autospec=True,
    )

    def side_effect(self, id, **kwargs):
        mem = projects[id]
        return V1Project(
            id=mem.project_id,
            name=mem.name,
            display_name=mem.display_name,
            owner_id=mem.owner_id,
            owner_type=mem.owner_type,
            project_settings=V1ProjectSettings(start_studio_on_spot_instance=True),
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        side_effect=side_effect,
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def resolve_all_teamspaces_api_mocker(mocker):
    projects = [
        V1Membership(
            name="ts-abc", display_name="ts-abc", project_id="ts-abc001", owner_id="org-abc", owner_type="organization"
        ),
        V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-abc", owner_type="organization"
        ),
        V1Membership(
            name="ts-abc", display_name="ts-abc", project_id="ts-abc002", owner_id="user-abc", owner_type="user"
        ),
        V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def002", owner_id="user-abc", owner_type="user"
        ),
    ]

    def side_effect_list(self, **kwargs):
        return V1ListMembershipsResponse(projects)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_memberships",
        side_effect=side_effect_list,
        autospec=True,
    )

    def side_effect(self, id, **kwargs):
        for mem in projects:
            if mem.project_id == id:
                return V1Project(
                    id=mem.project_id,
                    name=mem.name,
                    display_name=mem.display_name,
                    owner_id=mem.owner_id,
                    owner_type=mem.owner_type,
                )

        raise RuntimeError(f"No project found for {id=}")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        side_effect=side_effect,
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_get_studio(mocker):
    def list_cloudspaces(self, project_id, name):
        if name in ["st-abc", "st-def"]:
            print(name)
            return V1ListCloudSpacesResponse([V1CloudSpace(name=name, display_name=name)])
        return V1ListCloudSpacesResponse([])

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        side_effect=list_cloudspaces,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_create_studio(mocker):
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

    mock_create_cloud_space = mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mock_create_lightning_run = mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put", autospec=True)

    yield (mock_create_cloud_space, mock_create_lightning_run)

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_studio_status(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            requested=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(initial_restore_finished=False)
            )
        ),
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_switch_machine(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
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
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_start_studio(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
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
        ),
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_stop_studio(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_stop_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_run_command(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(
            exit_code=0, output="Command Started Successfully", session_name="session-name"
        ),
    )
    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api"
        ".CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
        autospec=True,
        return_value=resp,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_delete(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_delete_cloud_space",
        autospec=True,
        return_value=V1DeleteCloudSpaceResponse(),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_get_machine(mocker):
    def _side_effect(self, project_id, id, **kwargs):
        instance = None

        if id == "st-abc":
            instance = "cpu-4"
        elif id == "st-def":
            instance = "data-large"
        elif id == "st-ghi":
            instance = "g4dn.2xlarge"
        elif id == "st-jkl":
            instance = "g4dn.12xlarge"
        elif id == "st-mno":
            instance = "g6.4xlarge"
        elif id == "st-pqr":
            instance = "g6.12xlarge"
        elif id == "st-stu":
            instance = "g5.8xlarge"
        elif id == "st-vwx":
            instance = "g5.12xlarge"
        elif id == "st-yza":
            instance = "p4d.24xlarge"
        elif id == "st-bcd":
            instance = "p5.48xlarge"
        elif id == "st-efg":
            instance = "p5en.48xlarge"
        elif id == "st-hij":
            instance = "data-max"
        elif id == "st-klm":
            instance = "data-ultra"
        elif id == "st-nop":
            instance = "m3.medium"
        elif id == "st-qrs":
            instance = "g5.48xlarge"
        elif id == "st-tuv":
            instance = "g6e.4xlarge"
        elif id == "st-wxy":
            instance = "g6e.12xlarge"
        elif id == "st-zab":
            instance = "g6e.48xlarge"
        elif id == "st-cde":
            instance = "g6.48xlarge"
        elif id == "st-fgh":
            instance = "a2-ultragpu-2g"
        elif id == "st-ijk":
            instance = "a2-ultragpu-4g"
        elif id == "st-lmn":
            instance = "a4-highgpu-8g"
        elif id == "st-opq":
            instance = "n2d-standard-2"
        elif id == "st-rst":
            instance = "g2-standard-24"

        assert instance is not None
        return V1CloudSpaceInstanceConfig(compute_config=V1UserRequestedComputeConfig(name=instance))

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
        autospec=True,
        side_effect=_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_duplicate_user(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        return_value=V1Project(
            id="ts-abc", name="teamspace-abc", display_name="Teamspace ABC", owner_id="user-abc", owner_type="user"
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.user_service_api.UserServiceApi.user_service_search_users",
        return_value=V1SearchUsersResponse(users=[V1SearchUser(id="user-abc", username="user-abc")]),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_get_user",
        return_value=V1GetUserResponse(id="user-abc", username="user-abc"),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
        return_value=V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de"),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
        return_value=V1CloudSpace(
            name="st-abc-de", display_name="st-abc-de", id="st-abc-de", state=V1CloudSpaceState.READY
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        ),
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_duplicate_org(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        return_value=V1Project(
            id="ts-abc",
            name="teamspace-abc",
            display_name="Teamspace ABC",
            owner_id="org-abc",
            owner_type="organization",
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
        return_value=V1Organization(name="org-abc", display_name="org-abc", id="org-abc"),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
        return_value=V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de"),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
        return_value=V1CloudSpace(
            name="st-abc-de",
            display_name="st-abc-de",
            id="st-abc-de",
            state=V1CloudSpaceState.READY,
            cluster_id="c-abc",
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        ),
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_init_mocker(mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker):
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        # V1CloudSpace(name="st-abc", display_name="st-abc", cluster_id=None, project_id="ts-abc", id="st-abc"),
        # V1CloudSpace(name="st-def", display_name="st-def", cluster_id="c-abc", project_id="ts-abc", id="st-def"),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-def", project_id="ts-abc", id="st-def"
        ),
    }

    def _create_cloudspace_side_effect(self, body, project_id, **kwargs):
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

    def _list_cloudspaces_side_effect(self, project_id, name, **kwargs):
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_lightning_run_side_effect(self, body, project_id, cloudspace_id, **kwargs):
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        side_effect=_list_cloudspaces_side_effect,
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        autospec=True,
        return_type=V1PluginsListResponse(),
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
        return_value=V1PluginsListResponse(),
        autospec=True,
    )

    yield [mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_status_mocker(mocker):
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

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        autospec=True,
        side_effect=_get_status_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_start_mocker(mocker):
    # none since no instance available before start
    # use dict here so that it automatically uses global scope. Assignments to variables would introduce shadowing
    status = {"st-abc": None}
    machines = {"st-abc": None}

    def side_effect_start(self, body, project_id, id):
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

    def side_effect_get_cloud_space_instance_config(self, project_id: str, id: str):
        return V1CloudSpaceInstanceConfig(compute_config=machines[id])

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
        autospec=True,
        side_effect=side_effect_get_cloud_space_instance_config,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        side_effect=side_effect_status,
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        side_effect=side_effect_start,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_stop_mocker(mocker):
    status = {"st-abc": "CLOUD_SPACE_INSTANCE_STATE_RUNNING"}

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        )

    def side_effect_stop(self, project_id, id):
        assert id == "st-abc"
        status[id] = None
        return mock.MagicMock()

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_stop_cloud_space_instance",
        autospec=True,
        side_effect=side_effect_stop,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        side_effect=side_effect_status,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_delete_mocker(mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker):
    existing_studios = [
        V1CloudSpace(name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"),
    ]

    def _create_cloudspace_side_effect(self, body, project_id, **kwargs):
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
        )
        existing_studios.append(cloudspace)
        return cloudspace

    def _list_cloudspaces_side_effect(*args, **kwargs):
        return V1ListCloudSpacesResponse(existing_studios)

    def _create_lightning_run_side_effect(self, body, project_id, cloudspace_id, **kwargs):
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    def _delete_side_effect(self, project_id, id):
        to_pop = []
        for i, x in enumerate(existing_studios):
            if x.id == id:
                to_pop.append(i)

        for i in reversed(to_pop):
            existing_studios.pop(i)

        return V1DeleteCloudSpaceResponse()

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_delete_cloud_space",
        autospec=True,
        side_effect=_delete_side_effect,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        side_effect=_list_cloudspaces_side_effect,
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put")

    yield [mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_switch_mocker(mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker):
    # none since no instance available before start
    # use dict here so that it automatically uses global scope. Assignments to variables would introduce shadowing
    status = {"st-abc": None}
    requested_status = {"st-abc": None}
    requested_machines = {}
    machines = {"st-abc": V1UserRequestedComputeConfig(name="cpu-4")}

    def side_effect_start(self, body, project_id, id):
        status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase=status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            ),
            requested=Externalv1CloudSpaceInstanceStatus(
                phase=requested_status["st-abc"],
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            ),
        )

    def side_effect_switch_machines(self, project_id, id):
        machines[id] = requested_machines.pop(id)
        return mock.MagicMock()

    def side_effect_update_instance_config(self, body: IdCodeconfigBody, project_id: str, id: str):
        requested_machines[id] = body.compute_config
        requested_status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        return mock.MagicMock()

    def side_effect_get_cloud_space_instance_config(self, project_id: str, id: str):
        return V1CloudSpaceInstanceConfig(compute_config=machines[id])

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
        autospec=True,
        side_effect=side_effect_update_instance_config,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
        autospec=True,
        side_effect=side_effect_switch_machines,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
        autospec=True,
        side_effect=side_effect_get_cloud_space_instance_config,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        side_effect=side_effect_status,
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        side_effect=side_effect_start,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_run_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api"
        ".CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted"),
    )

    resp = _DummyResponse
    resp.data = (
        b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n'
        b'{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api"
        ".CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
        autospec=True,
        return_value=resp,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_run_error_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Submitted Successfully"),
    )

    resp = _DummyResponse
    resp.data = b'{"result":{"output":" No such file or directory foo ","exitCode":1}}\n'

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
        autospec=True,
        return_value=resp,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_duplicate_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
        return_value=V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de"),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
        return_value=V1CloudSpace(
            name="st-abc-de", display_name="st-abc-de", id="st-abc-de", state=V1CloudSpaceState.READY
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                startup_status=V1CloudSpaceInstanceStartupStatus(
                    initial_restore_finished=True, top_up_restore_finished=True
                ),
            )
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_install_plugin_mocker(mocker):
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

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_install_plugin",
        autospec=True,
        side_effect=_plugin_install_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_uninstall_plugin_mocker(mocker):
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

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_uninstall_plugin",
        autospec=True,
        side_effect=_plugin_uninstall_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_execute_plugin_mocker(mocker):
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

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_plugin",
        autospec=True,
        side_effect=_plugin_execute_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_list_available_plugins_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
        autospec=True,
        return_value=V1PluginsListResponse(
            plugins={"plugin1": "description1", "plugin2": "description2", "plugin3": "description3"}
        ),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_list_installed_plugins_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        autospec=True,
        return_value=V1PluginsListResponse(
            plugins={
                "plugin1": "description1",
                "plugin2": "description2",
            }
        ),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_create_app_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        if id == "job":
            assert body.plugin_arguments == {
                "entrypoint": "my-entry-point",
                "name": "fancy-job-name",
                "compute": "g5.8xlarge",
                "spot": "false",
            }
        elif id == "distributed_plugin":
            assert body.plugin_arguments == {
                "entrypoint": "my-entry-point",
                "name": "fancy-mmt-name",
                "distributedArguments": json.dumps(
                    {"cloud_compute": "g5.8xlarge", "num_instances": 4, "strategy": "parallel"}
                ),
                "spot": "false",
            }

        elif id == "inference_plugin":
            assert body.plugin_arguments == {
                "compute": "g5.8xlarge",
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

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_init_plugin_mocker(mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker):
    existing_studios = {
        "st-abc": V1CloudSpace(
            name="st-abc",
            display_name="st-abc",
            cluster_id="c-abc",
            project_id="ts-abc",
            id="st-abc",
            code_status=V1GetCloudSpaceInstanceStatusResponse(
                in_use=Externalv1CloudSpaceInstanceStatus(
                    phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
                    startup_status=V1CloudSpaceInstanceStartupStatus(
                        initial_restore_finished=True, top_up_restore_finished=True
                    ),
                )
            ),
        ),
        "st-def": V1CloudSpace(
            name="st-def",
            display_name="st-def",
            cluster_id="c-abc",
            project_id="ts-abc",
            id="st-def",
            code_status=V1GetCloudSpaceInstanceStatusResponse(
                in_use=Externalv1CloudSpaceInstanceStatus(
                    phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
                    startup_status=V1CloudSpaceInstanceStartupStatus(
                        initial_restore_finished=True, top_up_restore_finished=True
                    ),
                )
            ),
        ),
    }

    def _create_cloudspace_side_effect(self, body, project_id, **kwargs):
        assert isinstance(body, ProjectIdCloudspacesBody)
        cloudspace = V1CloudSpace(
            name=body.name,
            display_name=body.display_name,
            cluster_id=body.cluster_id,
            project_id=project_id,
            id=body.name,
            code_status=V1GetCloudSpaceInstanceStatusResponse(
                in_use=Externalv1CloudSpaceInstanceStatus(
                    phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING",
                    startup_status=V1CloudSpaceInstanceStartupStatus(
                        initial_restore_finished=True, top_up_restore_finished=True
                    ),
                )
            ),
        )
        existing_studios[cloudspace.name] = cloudspace
        return cloudspace

    def _list_cloudspaces_side_effect(self, project_id, name):
        if name in existing_studios:
            return V1ListCloudSpacesResponse([existing_studios[name]])
        return V1ListCloudSpacesResponse([])

    def _create_lightning_run_side_effect(self, body, project_id, cloudspace_id, **kwargs):
        return V1LightningRun(
            cluster_id=body.cluster_id, cloudspace_id=cloudspace_id, project_id=project_id, id=cloudspace_id + "_run"
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        side_effect=_list_cloudspaces_side_effect,
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put")

    return_value = V1PluginsListResponse(plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"})
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
        return_value=return_value,
        autospec=True,
    )

    yield [mocker, internal_get_org_api_mocker, internal_teamspace_api_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_installed_plugins_mocker(mocker):
    return_value = V1PluginsListResponse(plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"})
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        return_value=return_value,
        autospec=True,
    )

    return [mocker]


@pytest.fixture()
def internal_studio_plugin_install_mocker(mocker):
    return_value = V1PluginsListResponse(plugins={})

    def _side_effect_list(*args, **kwargs):
        return return_value

    def _side_effect_install(*args, **kwargs):
        nonlocal return_value
        return_value = V1PluginsListResponse(plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"})
        return V1Plugin(state="installation_success", error="")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        autospec=True,
        side_effect=_side_effect_list,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_install_plugin",
        autospec=True,
        side_effect=_side_effect_install,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_plugin_uninstall_mocker(mocker):
    return_value = V1PluginsListResponse(plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"})

    def _side_effect_list(*args, **kwargs):
        return return_value

    def _side_effect_uninstall(*args, **kwargs):
        nonlocal return_value
        return_value = V1PluginsListResponse(plugins={})
        return V1Plugin(state="uninstallation_success", error="")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        autospec=True,
        side_effect=_side_effect_list,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_install_plugin",
        autospec=True,
        return_value=V1Plugin(state="installation_success", error=""),
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_uninstall_plugin",
        autospec=True,
        side_effect=_side_effect_uninstall,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_plugin_run_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_plugin",
        autospec=True,
        return_value=V1Plugin(state="execution_success", error="", additional_info='{"port": 0}'),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_get_cloudspace_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
        return_value=V1CloudSpace(
            name="st-abc-de",
            display_name="st-abc-de",
            id="st-abc-de",
            cluster_id="c-abc",
        ),
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.machine import Machine

        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] != ""
        assert body.plugin_arguments["compute"] in [
            machine.instance_type for machine in Machine.__dict__.values() if isinstance(machine, Machine)
        ]

        return V1CreateCloudSpaceAppInstanceResponse(
            lightningappinstance=Externalv1LightningappInstance(
                name=body.plugin_arguments["name"],
                project_id="ts-abc",
                spec=V1LightningappInstanceSpec(cloud_space_id="st-abc"),
            )
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_mmt_run_mocker(mocker):
    def side_effect(self, body: ProjectIdMultimachinejobsBody, project_id):
        from lightning_sdk.machine import Machine

        assert body.spec.command == "python my-file.py"
        assert body.name == "my-fancy-mmt-name"
        assert body.machines == 42
        assert body.spec.instance_name in [
            machine.instance_type for machine in Machine.__dict__.values() if isinstance(machine, Machine)
        ]
        assert body.spec.cloudspace_id != ""

        return V1MultiMachineJob(
            cloudspace_id="st-abc",
            project_id="ts-abc",
            name="my-fancy-mmt-name",
            machines=42,
            spec=body.spec,
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_create_multi_machine_job",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_inference_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.machine import Machine

        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] == "my-fancy-inference-name"
        assert body.plugin_arguments["min_replicas"] == "1"
        assert body.plugin_arguments["max_replicas"] == "5"
        assert body.plugin_arguments["max_batch_size"] == "10"
        assert body.plugin_arguments["timeout_batching"] == "0.3"
        assert body.plugin_arguments["scale_in_interval"] == "11"
        assert body.plugin_arguments["scale_out_interval"] == "12"
        assert body.plugin_arguments["endpoint"] == "/fancy-predict"
        assert body.plugin_arguments["compute"] in [
            machine.instance_type for machine in Machine.__dict__.values() if isinstance(machine, Machine)
        ]

        return V1CreateCloudSpaceAppInstanceResponse(
            lightningappinstance=Externalv1LightningappInstance(name=body.plugin_arguments["name"])
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_requests_put_mocker(mocker):
    mocker.patch("requests.put", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_requests_get_mocker(mocker):
    mocker.patch("requests.get", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_login(mocker):  # noqa: PT004 # todo
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login",
        autospec=True,
        return_value=V1LoginResponse(token="token"),
    )


@pytest.fixture()
def internal_studio_api_start_new_port_mocker(mocker):  # todo
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_create_endpoint",
        autospec=True,
        return_value=V1Endpoint(
            id="endpoint-id",
            name="endpoint-name",
            urls=["http://localhost:8000"],
        ),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_data_prep_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.machine import Machine

        distributed_args = json.loads(body.plugin_arguments["dataPrepArguments"])
        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] == "my-fancy-data-prep-name"
        assert distributed_args["num_instances"] == 42
        assert distributed_args["cloud_compute"] in [
            machine.instance_type for machine in Machine.__dict__.values() if isinstance(machine, Machine)
        ]

        return V1CreateCloudSpaceAppInstanceResponse(
            lightningappinstance=Externalv1LightningappInstance(name=body.plugin_arguments["name"])
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space_app_instance",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_teamspace_api_list_mocker(mocker):
    project_memberships = [
        V1Membership(
            name="ts-abc", display_name="ts-abc", project_id="ts-abc001", owner_id="org-abc", owner_type="organization"
        ),
        V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-abc", owner_type="organization"
        ),
        V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-def", owner_type="organization"
        ),
        V1Membership(
            name="ts-abc", display_name="ts-abc", project_id="ts-abc002", owner_id="user-abc", owner_type="user"
        ),
        V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def002", owner_id="user-abc", owner_type="user"
        ),
        V1Membership(
            name="ts-def", display_name="ts-def", project_id="ts-def002", owner_id="user-def", owner_type="user"
        ),
    ]
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_memberships",
        return_value=V1ListMembershipsResponse(project_memberships),
        autospec=True,
    )

    def side_effect(self, id, **kwargs):
        for member in project_memberships:
            if member.project_id == id:
                return V1Project(
                    id=member.project_id,
                    name=member.name,
                    display_name=member.display_name,
                    owner_id=member.owner_id,
                    owner_type=member.owner_type,
                    project_settings=V1ProjectSettings(preferred_cluster="cluster-abc"),
                )

        return None

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        side_effect=side_effect,
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_list_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        autospec=True,
        return_type=V1PluginsListResponse(),
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_available_plugins",
        return_value=V1PluginsListResponse(),
        autospec=True,
    )

    return_values = [
        V1ListCloudSpacesResponse(
            cloudspaces=[
                V1CloudSpace(name="cs-abc", id="cs-abc"),
                V1CloudSpace(name="cs-def", id="cs-def"),
            ],
            next_page_token="next-page",
        ),
        V1ListCloudSpacesResponse(
            cloudspaces=[V1CloudSpace(name="cs-ghi", id="cs-ghi")],
            previous_page_token="prev-page",
            next_page_token=None,
        ),
    ]

    def side_effect(self, **kwargs):
        ret_val = return_values[0] if not kwargs.get("page_token", None) else return_values[1]

        project_id = kwargs["project_id"]
        cluster_id = kwargs.get("cluster_id", None)

        for i, cs in enumerate(ret_val.cloudspaces):
            cs._project_id = project_id
            cs._cluster_id = cluster_id
            ret_val._cloudspaces[i] = cs

        return ret_val

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        autospec=True,
        side_effect=side_effect,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        autospec=True,
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING")
        ),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_teamspace_api_cluster_list_mocker(mocker):  # noqa: PT004 # todo
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_project_cluster_bindings",
        autospec=True,
        return_value=V1ListProjectClusterBindingsResponse(
            clusters=[
                V1ProjectClusterBinding(cluster_id="cluster-abc", cluster_name="cluster-abc"),
                V1ProjectClusterBinding(cluster_id="cluster-def", cluster_name="cluster-def"),
            ]
        ),
    )


@pytest.fixture(autouse=True)
def keep_alive_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_keep_alive_cloud_space_instance",
        autospec=True,
    )

    def side_effect(self, teamspace_id, studio_id):
        keep_alive_freq = os.environ.get("LIGHTNING_KEEPALIVE_FREQUENCY", 30)
        key = f"{teamspace_id}-{studio_id}"
        while not self._keep_alive_events[key].is_set():
            time.sleep(keep_alive_freq)

    mocker.patch("lightning_sdk.api.studio_api.StudioApi._send_keepalives", side_effect=side_effect, autospec=True)
    mocker.patch("threading.Thread", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_slurm_run_mocker(mocker, monkeypatch):
    def cluster_service_list_project_clusters_side_effect(self, project_id):
        assert project_id == "ts-abc001"
        return V1ListProjectClustersResponse(
            clusters=[
                Externalv1Cluster(
                    id="slurm-cluster",
                    spec=V1ClusterSpec(slurm_v1=True),
                    status=V1ClusterStatus(phase=V1ClusterState.RUNNING),
                )
            ]
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cluster_service_api.ClusterServiceApi.cluster_service_list_project_clusters",
        autospec=True,
        side_effect=cluster_service_list_project_clusters_side_effect,
    )

    def slurm_jobs_user_service_create_user_slurm_job_side_effect(self, project_id, body):
        assert project_id == "ts-abc001"
        assert body.cloudspace_id == "st-ghi"
        assert body.cluster_id == "slurm-cluster"
        assert "LIGHTNING_CLOUD_PROJECT_ID" in body.command
        assert "LIGHTNING_USERNAME" in body.command
        assert "LIGHTNING_USER_ID" in body.command
        assert "LIGHTNING_API_KEY" in body.command
        assert "LIGHTNING_SERVICE_EXECUTION_ID=service_id" in body.command
        assert "python my-file.py" in body.command
        assert body.service_id == "service_id"
        assert body.sync_env is True
        assert body.work_dir == "/home/lightning_manager"
        assert body.cache_id == "2"

        return V1SLURMJob(name="slurm")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.slurm_jobs_user_service_api.SlurmJobsUserServiceApi.slurm_jobs_user_service_create_user_slurm_job",
        autospec=True,
        side_effect=slurm_jobs_user_service_create_user_slurm_job_side_effect,
    )

    monkeypatch.setenv("LIGHTNING_SERVICE_EXECUTION_ID", "service_id")

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def mocker_auth(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.rest_client.Auth",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_get_job(mocker):
    def find_instance(self, project_id, name):
        if name in ["j-abc", "j-def"]:
            return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_get_job_status(mocker):
    def find_instance(self, project_id, name):
        return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )

    phases = {
        "j-abc": None,
        "j-def": V1LightningappInstanceState.UNSPECIFIED,
        "j-ghi": V1LightningappInstanceState.IMAGE_BUILDING,
        "j-jkl": V1LightningappInstanceState.NOT_STARTED,
        "j-mno": V1LightningappInstanceState.PENDING,
        "j-pqr": V1LightningappInstanceState.RUNNING,
        "j-stu": V1LightningappInstanceState.FAILED,
        "j-vwx": V1LightningappInstanceState.STOPPED,
        "j-yz": V1LightningappInstanceState.COMPLETED,
    }

    def get_instance_status(self, project_id, id):
        return Externalv1LightningappInstance(
            name=id, project_id=project_id, id=id, status=V1LightningappInstanceStatus(phase=phases[id])
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_get_lightningapp_instance",
        side_effect=get_instance_status,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_get_job_status_v2(mocker):
    def find_job(self, project_id, name):
        return V1Job(id=name, spec=V1JobSpec(cloudspace_id="st-abc"), project_id=project_id)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_find_job",
        side_effect=find_job,
        autospec=True,
    )

    phases = {
        "j-abc": None,
        "j-def": "unknown",
        "j-ghi": "pending",
        "j-jkl": "running",
        "j-mno": "failed",
        "j-pqr": "stopped",
        "j-stu": "completed",
    }

    def get_job(self, project_id, id):
        return V1Job(name=id, project_id=project_id, id=id, state=phases[id])

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_get_job",
        side_effect=get_job,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_stop_job(mocker):
    status = {"j-abc": V1LightningappInstanceState.RUNNING}

    def find_instance(self, project_id, name):
        if name in ["j-abc", "j-def"]:
            return Externalv1LightningappInstance(
                name=name, project_id=project_id, id=name, status=V1LightningappInstanceStatus(phase=status[name])
            )
        raise ApiException(status=404)

    def get_instance(self, project_id, id):
        if id in ["j-abc", "j-def"]:
            return Externalv1LightningappInstance(
                name=id, project_id=project_id, id=id, status=V1LightningappInstanceStatus(phase=status[id])
            )
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_get_lightningapp_instance",
        side_effect=get_instance,
        autospec=True,
    )

    def update_state(self, project_id, id, body):
        status[id] = body.spec.desired_state

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_update_lightningapp_instance",
        side_effect=update_state,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_delete_job(mocker):
    names = ["j-abc", "j-def"]
    status = {"j-abc": V1LightningappInstanceState.RUNNING}

    def find_instance(self, project_id, name):
        if name in names:
            return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )

    def get_instance(self, project_id, id):
        if id in ["j-abc", "j-def"]:
            return Externalv1LightningappInstance(
                name=id, project_id=project_id, id=id, status=V1LightningappInstanceStatus(phase=status[id])
            )
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_get_lightningapp_instance",
        side_effect=get_instance,
        autospec=True,
    )

    def delete_instance(self, project_id, id):
        names.remove(id)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_delete_lightningapp_instance",
        side_effect=delete_instance,
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_delete_job_v2(mocker):
    names = ["j-abc", "j-def"]

    def find_job(self, project_id, name):
        if name in names:
            return V1Job(name=name, project_id=project_id, id=name, spec=V1JobSpec())
        raise ApiException(status=404)

    def get_job(self, project_id, id):
        if id in names:
            return V1Job(name=id, project_id=project_id, id=id, spec=V1JobSpec())
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_find_job",
        side_effect=find_job,
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_get_job",
        side_effect=get_job,
        autospec=True,
    )

    def delete_job(self, project_id, id, cloudspace_id=""):
        names.remove(id)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_delete_job",
        side_effect=delete_job,
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_get_work(mocker):
    def find_instance(self, project_id, name):
        if name == "j-abc":
            return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )

    def get_instance(self, project_id, id):
        if id == "j-abc":
            return Externalv1LightningappInstance(name=id, project_id=project_id, id=id)
        raise ApiException(status=404)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_get_lightningapp_instance",
        side_effect=get_instance,
        autospec=True,
    )

    def list_works(self, project_id, app_id):
        return V1ListLightningworkResponse(
            lightningworks=[
                Externalv1Lightningwork(
                    display_name="work abc",
                    name="root.w-abc",
                    id="w-abc",
                    project_id=project_id,
                    spec=V1LightningworkSpec(
                        user_requested_compute_config=V1UserRequestedComputeConfig(name="g4dn.12xlarge")
                    ),
                )
            ]
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningwork_service_api.LightningworkServiceApi.lightningwork_service_list_lightningwork",
        side_effect=list_works,
        autospec=True,
    )

    def get_work(self, project_id, app_id, id):
        return Externalv1Lightningwork(
            display_name="work abc",
            name="root.w-abc",
            id="w-abc",
            project_id=project_id,
            spec=V1LightningworkSpec(user_requested_compute_config=V1UserRequestedComputeConfig(name="g4dn.12xlarge")),
            status=V1LightningworkStatus(phase=V1LightningworkState.STOPPED),
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningwork_service_api.LightningworkServiceApi.lightningwork_service_get_lightningwork",
        side_effect=get_work,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_api_mocker_all_jobs_valid(mocker):
    def find_instance(self, project_id, name):
        return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_teamspace_api_create_agent_mocker(mocker):
    def create_agent(self, body, project_id, **kwargs):
        return V1Assistant(name=body.name, project_id=project_id, id=body.name, model=body.model)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.assistants_service_api.AssistantsServiceApi.assistants_service_create_assistant",
        side_effect=create_agent,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_agents_api_get_agent_mocker(mocker):
    def get_agent(self, id):
        return V1Assistant(name=id, id=id, project_id="project_id", model="model", endpoint_id="enpoint_id")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.assistants_service_api.AssistantsServiceApi.assistants_service_get_assistant",
        side_effect=get_agent,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_agents_api_delete_agent_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.assistants_service_api.AssistantsServiceApi.assistants_service_delete_assistant",
        return_value=None,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_agents_api_update_agent_mocker(mocker):
    def update_agent(self, id, project_id, body):
        return V1Assistant(name=body.name, project_id=project_id, id=id)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.assistants_service_api.AssistantsServiceApi.assistants_service_update_assistant",
        side_effect=update_agent,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_agents_api_update_agent_endpoint_mocker(mocker):
    def update_agent_endpoint(self, project_id, id, body, **kwargs):
        return V1Endpoint(openai=V1UpstreamOpenAI(base_url=body.openai.base_url, api_key=body.openai.api_key))

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_update_endpoint",
        side_effect=update_agent_endpoint,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_agents_api_get_agent_endpoint_mocker(mocker):
    def get_agent_endpoint(self, project_id, ref):
        return V1Endpoint(
            id=ref, project_id=project_id, openai=V1UpstreamOpenAI(base_url="https://api.openai.com", api_key="api_key")
        )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.endpoint_service_api.EndpointServiceApi.endpoint_service_get_endpoint",
        side_effect=get_agent_endpoint,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_agent_api_create_assistant_managed_endpoint_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.assistants_service_api.AssistantsServiceApi.assistants_service_create_assistant_managed_endpoint",
        return_value=V1CreateManagedEndpointResponse(endpoint=V1ManagedEndpoint(id="test-managed-endpoint")),
        autospec=True,
    )

    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def internal_agent_api_create_assistant_mocker(mocker):
    def create_assistant(self, body, project_id):
        return V1Assistant(id="test-assistant", name="test-assistant")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.assistants_service_api.AssistantsServiceApi.assistants_service_create_assistant",
        side_effect=create_assistant,
        autospec=True,
    )

    yield [mocker]
    mocker.resetall()


@pytest.fixture(scope="session")
def available_aws_instance_types():
    import boto3

    # Initialize empty list to store instance types
    instance_types = []
    for region in ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]:
        # supress exceptions
        with suppress(Exception):
            # Create EC2 client
            ec2_client = boto3.client("ec2", region_name=region)
            # Paginator to handle large result sets
            paginator = ec2_client.get_paginator("describe_instance_types")
            # Iterate through each page of instance types
            for page in paginator.paginate():
                instance_types += [it["InstanceType"] for it in page["InstanceTypes"]]

    return set(instance_types)


@pytest.fixture()
def job_api_get_job_by_name_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_find_job",
        autospec=True,
        return_value=V1Job(id="test-job-id", spec=V1JobSpec(cloudspace_id="st-abc"), project_id="ts-abc"),
    )
    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def job_api_get_cloudspace_name(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space",
        return_value=V1CloudSpace(name="st-abc", display_name="st-abc", id="st-abc"),
        autospec=True,
    )

    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def job_api_get_job_by_id_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_get_job",
        autospec=True,
        return_value=V1Job(id="test-job-id", spec=V1JobSpec(cloudspace_id="st-abc"), state="completed"),
    )
    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def mmt_api_get_job_by_name_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_get_multi_machine_job_by_name",
        autospec=True,
        return_value=V1MultiMachineJob(id="test-job-id", spec=V1JobSpec(cloudspace_id=None)),
    )
    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def internal_job_logs_mocker(mocker):
    log_msg = "[2025-01-08T14:15:03.797142418Z] ⚡  ~ echo Hello\n[2025-01-08T14:15:03.803077717Z] Hello\n"
    dummy_url = "http://dummy-url.com/logs"

    class DummyOpener:
        def read(self) -> bytes:
            return log_msg.encode("utf-8")

    def side_effect(url):
        assert url == dummy_url
        return DummyOpener()

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_download_job_logs",
        autospec=True,
        return_value=V1DownloadJobLogsResponse(url=dummy_url),
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_download_lightningapp_instance_logs",
        autospec=True,
        return_value=V1DownloadLightningappInstanceLogsResponse(url=dummy_url),
    )

    mocker.patch(
        "lightning_sdk.api.job_api.urlopen",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_job_fallback_mocker(mocker):
    def v2_side_effect(*args, **kwargs):
        raise ApiException(status=404, reason="Not found")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_find_job",
        autospec=True,
        side_effect=v2_side_effect,
    )

    def find_instance(self, project_id, name):
        return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )
    yield [mocker]
    mocker.resetall()


@pytest.fixture()
def internal_mmt_fallback_mocker(mocker):
    def v2_side_effect(*args, **kwargs):
        raise ApiException(status=404, reason="Not found")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.jobs_service_api.JobsServiceApi.jobs_service_get_multi_machine_job_by_name",
        autospec=True,
        side_effect=v2_side_effect,
    )

    def find_instance(self, project_id, name):
        return Externalv1LightningappInstance(name=name, project_id=project_id, id=name)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_find_lightningapp_instance",
        side_effect=find_instance,
        autospec=True,
    )
    yield [mocker]
    mocker.resetall()
