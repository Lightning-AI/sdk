import json
import math
from unittest import mock
from unittest.mock import Mock

import pytest
from datetime import datetime

from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.openapi import (
    AppsIdBody1,
    Externalv1CloudSpaceInstanceStatus,
    Externalv1LightningappInstance,
    IdCodeconfigBody,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1CloudSpaceState,
    V1CloudSpaceInstanceConfig,
    V1CreateCloudSpaceAppInstanceResponse,
    V1DeleteCloudSpaceResponse,
    V1ExecuteCloudSpaceCommandResponse,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetUserResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListMembershipsResponse,
    V1ListOrganizationsResponse,
    V1Membership,
    V1PresignedUrl,
    V1Organization,
    V1Plugin,
    V1PluginsListResponse,
    V1Project,
    V1SearchUser,
    V1SearchUsersResponse,
    V1UploadProjectArtifactResponse,
    V1UserRequestedComputeConfig,
    V1LoginResponse,
    V1GetArtifactsPageResponse,
    V1Artifact,
    V1ListProjectClusterBindingsResponse,
    V1ProjectClusterBinding,
)

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

        assert _id and _name

        if _name == "xyx" or _id == "xyz":
            return

        return V1Organization(display_name=_name, name=_name, id=_id)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
        side_effect=side_effect,
        autospec=True,
    )
    yield [mocker, internal_auth_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_teamspace_api_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_memberships",
        return_value=V1ListMembershipsResponse(
            [
                V1Membership(name="ts-abc", display_name="ts-abc", project_id="ts-abc001", owner_id="org-abc"),
                V1Membership(name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-abc"),
            ]
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        return_value=V1Project(
            id="ts-abc", name="ts-abc", display_name="ts-abc", owner_id="org-abc", owner_type="organization"
        ),
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
    mocker.patch("requests.put", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_studio_status(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            requested=Externalv1CloudSpaceInstanceStatus(startup_percentage="0")
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
            requested=Externalv1CloudSpaceInstanceStatus(startup_percentage="100")
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
            requested=Externalv1CloudSpaceInstanceStatus(startup_percentage="100"),
            in_use=Externalv1CloudSpaceInstanceStatus(startup_percentage="100"),
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
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Command Started Successfully"),
    )
    resp = _DummyResponse
    resp.data = b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
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
            instance = "data-large-3000"
        elif id == "st-ghi":
            instance = "g4dn.2xlarge"
        elif id == "st-jkl":
            instance = "g4dn.12xlarge"
        elif id == "st-mno":
            instance = "p3.2xlarge"
        elif id == "st-pqr":
            instance = "p3.8xlarge"
        elif id == "st-stu":
            instance = "g5.8xlarge"
        elif id == "st-vwx":
            instance = "g5.12xlarge"
        elif id == "st-yza":
            instance = "p4d.24xlarge"

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
            in_use=Externalv1CloudSpaceInstanceStatus(startup_percentage="100", sync_in_progress=False)
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
            in_use=Externalv1CloudSpaceInstanceStatus(startup_percentage="100", sync_in_progress=False)
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
            name="st-def", display_name="st-def", cluster_id="c-abc", project_id="ts-abc", id="st-def"
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
        elif id == "st-stu":
            status = None
        elif id == "st-xyz":
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
        machines["st-abc"] = V1UserRequestedComputeConfig(name="cpu-4")
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(phase=status["st-abc"], startup_percentage="100")
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
            in_use=Externalv1CloudSpaceInstanceStatus(phase=status["st-abc"], startup_percentage="100")
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
            in_use=Externalv1CloudSpaceInstanceStatus(phase=status["st-abc"], startup_percentage="100"),
            requested=Externalv1CloudSpaceInstanceStatus(phase=requested_status["st-abc"], startup_percentage="100"),
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
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING", startup_percentage="100"
            )
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=0, output="Successfully submitted"),
    )

    resp = _DummyResponse
    resp.data = b'{"result":{"output":" foo-res","exitCode":0}}\n{"result":{"output":"ponse ba","exitCode":0}}\n{"result":{"output":"r-respon","exitCode":0}}\n{"result":{"output":"se ","exitCode":0}}\n'

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_long_running_command_in_cloud_space_stream",
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
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING", startup_percentage="100"
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
            in_use=Externalv1CloudSpaceInstanceStatus(startup_percentage="100", sync_in_progress=False)
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_install_plugin_mocker(mocker):
    def _plugin_install_side_effect(self, project_id, id, plugin_id):
        assert plugin_id == "my-fancy-plugin"
        if id == "st-abc":
            return V1Plugin(state="installation_success", error="")
        elif id == "st-def":
            return V1Plugin(state="installation_success", error="abc")
        elif id == "st-ghi":
            return V1Plugin(state="installation_error", error="")
        elif id == "st-jkl":
            return V1Plugin(state="installation_error", error="jkl")
        elif id == "st-mno":
            return V1Plugin(state="installation_success", error="", additional_info=" my-info \n")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_install_plugin",
        autospec=True,
        side_effect=_plugin_install_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_uninstall_plugin_mocker(mocker):
    def _plugin_uninstall_side_effect(self, project_id, id, plugin_id):
        assert plugin_id == "my-fancy-plugin"
        if id == "st-abc":
            return V1Plugin(state="uninstallation_success", error="")
        elif id == "st-def":
            return V1Plugin(state="uninstallation_success", error="abc")
        elif id == "st-ghi":
            return V1Plugin(state="uninstallation_error", error="")
        elif id == "st-jkl":
            return V1Plugin(state="uninstallation_error", error="jkl")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_uninstall_plugin",
        autospec=True,
        side_effect=_plugin_uninstall_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_execute_plugin_mocker(mocker):
    def _plugin_execute_side_effect(self, project_id, id, plugin_id):
        assert plugin_id == "my-fancy-plugin"
        if id == "st-abc":
            return V1Plugin(state="execution_success", error="", additional_info='{"port": 0}')
        elif id == "st-def":
            return V1Plugin(state="execution_success", error="", additional_info='{"port": 1}')
        elif id == "st-ghi":
            return V1Plugin(state="execution_success", error="", additional_info='{"port": -1}')
        elif id == "st-jkl":
            return V1Plugin(state="execution_success", error="jkl")
        elif id == "st-mno":
            return V1Plugin(state="execution_error", error="")
        elif id == "st-pqr":
            return V1Plugin(state="execution_error", error="pqr")

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_plugin",
        autospec=True,
        side_effect=_plugin_execute_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
def internal_studio_api_create_app_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        if id == "job":
            assert body.plugin_arguments == {
                "entrypoint": "my-entry-point",
                "name": "fancy-job-name",
                "compute": "g5.8xlarge",
            }
        elif id == "distributed_plugin":
            assert body.plugin_arguments == {
                "entrypoint": "my-entry-point",
                "name": "fancy-mmt-name",
                "distributedArguments": json.dumps(
                    {"cloud_compute": "g5.8xlarge", "num_instances": 4, "strategy": "parallel"}
                ),
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
            name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"
        ),
        "st-def": V1CloudSpace(
            name="st-def", display_name="st-def", cluster_id="c-abc", project_id="ts-abc", id="st-def"
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


@pytest.fixture
def internal_studio_installed_plugins_mocker(mocker):
    return_value = V1PluginsListResponse(plugins={"my-fancy-dummy-plugin": "Description of my fancy dummy plugin"})
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_installed_plugins",
        return_value=return_value,
        autospec=True,
    )

    yield [mocker]


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
def internal_studio_plugin_run_mocker(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_plugin",
        autospec=True,
        return_value=V1Plugin(state="execution_success", error="", additional_info='{"port": 0}'),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_job_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.api.studio_api import _MACHINE_TO_COMPUTE_NAME

        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] == "my-fancy-job-name"
        assert body.plugin_arguments["compute"] in _MACHINE_TO_COMPUTE_NAME.values()

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


@pytest.fixture
def internal_mmt_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.api.studio_api import _MACHINE_TO_COMPUTE_NAME

        distributed_args = json.loads(body.plugin_arguments["distributedArguments"])
        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] == "my-fancy-mmt-name"
        assert distributed_args["num_instances"] == 42
        assert distributed_args["strategy"] == "parallel"
        assert distributed_args["cloud_compute"] in _MACHINE_TO_COMPUTE_NAME.values()

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


@pytest.fixture
def internal_inference_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.api.studio_api import _MACHINE_TO_COMPUTE_NAME

        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] == "my-fancy-inference-name"
        assert body.plugin_arguments["min_replicas"] == "1"
        assert body.plugin_arguments["max_replicas"] == "5"
        assert body.plugin_arguments["max_batch_size"] == "10"
        assert body.plugin_arguments["timeout_batching"] == "0.3"
        assert body.plugin_arguments["scale_in_interval"] == "11"
        assert body.plugin_arguments["scale_out_interval"] == "12"
        assert body.plugin_arguments["endpoint"] == "/fancy-predict"
        assert body.plugin_arguments["compute"] in _MACHINE_TO_COMPUTE_NAME.values()

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


@pytest.fixture
def internal_studio_api_single_part_upload(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_upload_project_artifact",
        autospec=True,
        return_value=V1UploadProjectArtifactResponse(
            urls=[
                V1PresignedUrl(part_number=1, url=f"https://my-dummy-s3-url.com"),
            ],
        ),
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_complete_upload_project_artifact",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_multi_part_upload(mocker):
    num_parts = 2
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_upload_project_artifact",
        autospec=True,
        return_value=V1UploadProjectArtifactResponse(
            upload_id="my-fancy-upload",
            urls=[V1PresignedUrl(part_number=i, url=f"https://my-dummy-s3-url.com&part={i}") for i in range(num_parts)],
        ),
    )

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.lightningapp_instance_service_api.LightningappInstanceServiceApi.lightningapp_instance_service_complete_upload_project_artifact",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_requests_put_mocker(mocker):
    mocker.patch("requests.put", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_requests_get_mocker(mocker):
    mocker.patch("requests.get", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_login(mocker):
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.auth_service_api.AuthServiceApi.auth_service_login",
        autospec=True,
        return_value=V1LoginResponse(token="token"),
    )


@pytest.fixture
def internal_data_prep_run_mocker(mocker):
    def side_effect(self, body, project_id, cloudspace_id, id):
        from lightning_sdk.api.studio_api import _MACHINE_TO_COMPUTE_NAME

        distributed_args = json.loads(body.plugin_arguments["dataPrepArguments"])
        assert body.plugin_arguments["entrypoint"] == "python my-file.py"
        assert body.plugin_arguments["name"] == "my-fancy-data-prep-name"
        assert distributed_args["num_instances"] == 42
        assert distributed_args["cloud_compute"] in _MACHINE_TO_COMPUTE_NAME.values()

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
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_memberships",
        return_value=V1ListMembershipsResponse(
            [
                V1Membership(name="ts-abc", display_name="ts-abc", project_id="ts-abc001", owner_id="org-abc"),
                V1Membership(name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-abc"),
                V1Membership(name="ts-def", display_name="ts-def", project_id="ts-def001", owner_id="org-def"),
            ]
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        return_value=V1Project(
            id="ts-abc", name="ts-abc", display_name="ts-abc", owner_id="org-abc", owner_type="organization"
        ),
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_studio_api_list_mocker(mocker):
    return_values = [
        V1ListCloudSpacesResponse(
            cloudspaces=[
                V1CloudSpace(
                    name="cs-abc",
                    project_id="ts-abc",
                ),
                V1CloudSpace("cs-def", project_id="ts-abc"),
            ],
            next_page_token="next-page",
        ),
        V1ListCloudSpacesResponse(
            cloudspaces=[V1CloudSpace(name="cs-ghi", project_id="ts-abc")], previous_page_token="prev-page"
        ),
    ]

    def side_effect(*args, **kwargs):
        return return_values.pop(0)

    mocker.patch(
        "lightning_sdk.lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        autospec=True,
        side_effect=side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture
def internal_teamspace_api_cluster_list_mocker(mocker):
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
