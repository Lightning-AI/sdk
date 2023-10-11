from unittest import mock
from unittest.mock import Mock

import pytest
from lightning_sdk.lightning_cloud.openapi import (
    Externalv1CloudSpaceInstanceStatus,
    IdCodeconfigBody,
    ProjectIdCloudspacesBody,
    V1CloudSpace,
    V1CloudSpaceInstanceConfig,
    V1DeleteCloudSpaceResponse,
    V1ExecuteCloudSpaceCommandResponse,
    V1GetCloudSpaceInstanceStatusResponse,
    V1GetUserResponse,
    V1LightningRun,
    V1ListCloudSpacesResponse,
    V1ListMembershipsResponse,
    V1ListOrganizationsResponse,
    V1Membership,
    V1Organization,
    V1Project,
    V1SearchUser,
    V1SearchUsersResponse,
    V1UserRequestedComputeConfig,
)

_BEGIN_OUTPUT_TOKEN = "LIGHTNING_BEGIN_OUTPUT"
_END_OUTPUT_TOKEN = "LIGHTNING_END_OUTPUT"


@pytest.fixture()
def internal_user_api_mocker(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.user_service_api.UserServiceApi.user_service_search_users",
        return_value=V1SearchUsersResponse(
            users=[V1SearchUser(username="user-abc"), V1SearchUser(username="user-abc-de")]
        ),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_org_api_mocker(mocker):
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

    mocker.patch("lightning_cloud.openapi.api_client.ApiClient.call_api", side_effect=_side_effect_api_call)
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_teamspace_api_mocker(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_list_memberships",
        return_value=V1ListMembershipsResponse(
            [
                V1Membership(name="ts-abc", display_name="ts-abc", project_id="ts-abc001"),
                V1Membership(name="ts-def", display_name="ts-def", project_id="ts-def001"),
            ]
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        return_value=V1Project(
            id="ts-abc", name="ts-abc", display_name="ts-abc", owner_id="org-abc", owner_type="organization"
        ),
        autospec=True,
    )
    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_get_studio(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        return_value=V1ListCloudSpacesResponse(
            [V1CloudSpace(name="st-abc", display_name="st-abc"), V1CloudSpace(name="st-def", display_name="st-def")]
        ),
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
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put", autospec=True)

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_studio_status(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
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
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            requested=Externalv1CloudSpaceInstanceStatus(startup_percentage="100")
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_start_studio(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
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
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_stop_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_run_command(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=0, output=" foo-response bar-response "),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_delete(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_delete_cloud_space",
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
            instance = "data-large-8000"
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
        return V1CloudSpaceInstanceConfig(V1UserRequestedComputeConfig(name=instance))

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
        autospec=True,
        side_effect=_side_effect,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_api_mocker_duplicate_user(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
        return_value=V1Project(
            id="ts-abc", name="teamspace-abc", display_name="Teamspace ABC", owner_id="user-abc", owner_type="user"
        ),
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.user_service_api.UserServiceApi.user_service_search_users",
        return_value=V1SearchUsersResponse(users=[V1SearchUser(id="user-abc", username="user-abc")]),
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
        return_value=V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de"),
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
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
        "lightning_cloud.openapi.api.projects_service_api.ProjectsServiceApi.projects_service_get_project",
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
        "lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
        return_value=V1Organization(name="org-abc", display_name="org-abc", id="org-abc"),
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
        return_value=V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de"),
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(startup_percentage="100", sync_in_progress=False)
        ),
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_init_mocker(mocker, internal_org_api_mocker, internal_teamspace_api_mocker):
    existing_studios = [
        V1CloudSpace(name="st-abc", display_name="st-abc", cluster_id="c-abc", project_id="ts-abc", id="st-abc"),
        V1CloudSpace(name="st-abc", display_name="st-abc", cluster_id=None, project_id="ts-abc", id="st-abc"),
        V1CloudSpace(name="st-def", display_name="st-def", cluster_id="c-abc", project_id="ts-abc", id="st-def"),
        V1CloudSpace(name="st-def", display_name="st-def", cluster_id=None, project_id="ts-abc", id="st-def"),
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

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        side_effect=_list_cloudspaces_side_effect,
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put")

    yield [mocker, internal_org_api_mocker, internal_teamspace_api_mocker]

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

        return V1GetCloudSpaceInstanceStatusResponse(in_use=Externalv1CloudSpaceInstanceStatus(phase=status))

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
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

    def side_effect_start(self, project_id, id):
        status["st-abc"] = "CLOUD_SPACE_INSTANCE_STATE_RUNNING"
        return mock.MagicMock()

    def side_effect_status(*args, **kwargs):
        return V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(phase=status["st-abc"], startup_percentage="100")
        )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
        autospec=True,
        return_value=V1CloudSpaceInstanceConfig(V1UserRequestedComputeConfig(name="cpu-4")),
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        side_effect=side_effect_status,
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
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
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_stop_cloud_space_instance",
        autospec=True,
        side_effect=side_effect_stop,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        side_effect=side_effect_status,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_delete_mocker(mocker, internal_org_api_mocker, internal_teamspace_api_mocker):
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
        print(project_id, id)
        to_pop = []
        for i, x in enumerate(existing_studios):
            if x.id == id:
                to_pop.append(i)

        for i in reversed(to_pop):
            existing_studios.pop(i)

        return V1DeleteCloudSpaceResponse()

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_delete_cloud_space",
        autospec=True,
        side_effect=_delete_side_effect,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_list_cloud_spaces",
        side_effect=_list_cloudspaces_side_effect,
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_cloud_space",
        autospec=True,
        side_effect=_create_cloudspace_side_effect,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_create_lightning_run",
        autospec=True,
        side_effect=_create_lightning_run_side_effect,
    )
    mocker.patch("requests.put")

    yield [mocker, internal_org_api_mocker, internal_teamspace_api_mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_switch_mocker(mocker, internal_org_api_mocker, internal_teamspace_api_mocker):
    # none since no instance available before start
    # use dict here so that it automatically uses global scope. Assignments to variables would introduce shadowing
    status = {"st-abc": None}
    requested_status = {"st-abc": None}
    requested_machines = {}
    machines = {"st-abc": V1UserRequestedComputeConfig(name="cpu-4")}

    def side_effect_start(self, project_id, id):
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
        return V1CloudSpaceInstanceConfig(machines[id])

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_update_cloud_space_instance_config",
        autospec=True,
        side_effect=side_effect_update_instance_config,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_switch_cloud_space_instance",
        autospec=True,
        side_effect=side_effect_switch_machines,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_config",
        autospec=True,
        side_effect=side_effect_get_cloud_space_instance_config,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        side_effect=side_effect_status,
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        side_effect=side_effect_start,
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_run_mocker(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING", startup_percentage="100"
            )
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=0, output=" foo-response bar-response "),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_run_error_mocker(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(
                phase="CLOUD_SPACE_INSTANCE_STATE_RUNNING", startup_percentage="100"
            )
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_execute_command_in_cloud_space",
        autospec=True,
        return_value=V1ExecuteCloudSpaceCommandResponse(exit_code=1, output=" No such file or directory foo "),
    )

    yield [mocker]

    mocker.resetall()


@pytest.fixture()
def internal_studio_duplicate_mocker(mocker):
    mocker.patch(
        "lightning_cloud.openapi.api.organizations_service_api.OrganizationsServiceApi.organizations_service_get_organization",
        return_value=V1Organization(name="org-abc", display_name="org-abc", id="org-abc"),
        autospec=True,
    )
    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_fork_cloud_space",
        return_value=V1CloudSpace(name="st-abc-de", display_name="st-abc-de", id="st-abc-de"),
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_get_cloud_space_instance_status",
        return_value=V1GetCloudSpaceInstanceStatusResponse(
            in_use=Externalv1CloudSpaceInstanceStatus(startup_percentage="100", sync_in_progress=False)
        ),
        autospec=True,
    )

    mocker.patch(
        "lightning_cloud.openapi.api.cloud_space_service_api.CloudSpaceServiceApi.cloud_space_service_start_cloud_space_instance",
        autospec=True,
    )

    yield [mocker]

    mocker.resetall()
