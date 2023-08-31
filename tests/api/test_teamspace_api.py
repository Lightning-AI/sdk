from unittest import mock
from lightning_cloud.openapi import V1ListMembershipsResponse, V1Project, V1Membership
import pytest

@mock.patch("lightning.app.utilities.network.LightningClient")
def test_get_teamspace(_):
    # needs local import since patching needs to happen before import
    from lightning_sdk.api.teamspace_api import TeamspaceApi

    teamspace_api = TeamspaceApi()
    teamspace_api._client.projects_service_list_memberships.return_value = V1ListMembershipsResponse([
        V1Membership(name="abc", display_name="abc", project_id="abc001"),
        V1Membership(name="xyz", display_name="xyz", project_id="xyz001")
    ])
    teamspace_api._client.projects_service_get_project.return_value = V1Project()
    project = teamspace_api.get_teamspace("abc", "def")
    teamspace_api._client.projects_service_list_memberships.assert_called_once_with(organization_id="def")
    teamspace_api._client.projects_service_get_project.assert_called_once_with("abc001")
    assert isinstance(project, V1Project)

@mock.patch("lightning.app.utilities.network.LightningClient")
def test_get_teamspace_error(_):
     # needs local import since patching needs to happen before import
    from lightning_sdk.api.teamspace_api import TeamspaceApi

    teamspace_api = TeamspaceApi()
    teamspace_api._client.projects_service_list_memberships.return_value = V1ListMembershipsResponse([
        V1Membership(name="xyz", display_name="xyz", project_id="xyz001")
    ])

    with pytest.raises(ValueError, match="Teamspace abc does not exist"):
        teamspace_api.get_teamspace("abc", "def")
