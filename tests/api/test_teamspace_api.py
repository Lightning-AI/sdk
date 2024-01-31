import pytest

from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.lightning_cloud.openapi import V1Project


def test_get_teamspace(internal_teamspace_api_mocker):
    teamspace_api = TeamspaceApi()

    project = teamspace_api.get_teamspace("ts-abc", "org-def")
    assert isinstance(project, V1Project)


def test_get_teamspace_error(internal_teamspace_api_mocker):
    teamspace_api = TeamspaceApi()

    with pytest.raises(ValueError, match="Teamspace xyz does not exist"):
        teamspace_api.get_teamspace("xyz", "org-def")


def test_list_teamspaces(internal_teamspace_api_list_mocker):
    teamspace_api = TeamspaceApi()

    projects = teamspace_api.list_teamspaces("org-abc", name=None)
    assert len(projects) == 2
    assert isinstance(projects[0], V1Project)
    assert isinstance(projects[1], V1Project)

    projects = teamspace_api.list_teamspaces("org-def", name=None)
    assert len(projects) == 1
    assert isinstance(projects[0], V1Project)

    projects = teamspace_api.list_teamspaces("org-abc", name="ts-def")
    assert len(projects) == 1
    assert isinstance(projects[0], V1Project)

def test_list_studios(internal_studio_api_list_mocker):
    teamspace_api = TeamspaceApi()

    studios = teamspace_api.list_studios(cluster_id="cluster_abc", teamspace_id="ts-abc")

    assert len(studios) == 3


    

