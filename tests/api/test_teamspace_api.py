import pytest
import os
from unittest import mock
from pathlib import Path

from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.lightning_cloud.openapi import V1Project, V1ProjectClusterBinding, V1CloudSpace


def test_get_teamspace(internal_teamspace_api_mocker):
    teamspace_api = TeamspaceApi()

    project = teamspace_api.get_teamspace("ts-abc", "org-abc")
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
    for st in studios:
        assert isinstance(st, V1CloudSpace)


def test_list_clusters(internal_teamspace_api_cluster_list_mocker):
    teamspace_api = TeamspaceApi()

    clusters = teamspace_api.list_clusters(teamspace_id="ts-abc")

    assert len(clusters) == 2
    for cl in clusters:
        assert isinstance(cl, V1ProjectClusterBinding)


def test_create_agent(internal_teamspace_api_create_agent_mocker):
    teamspace_api = TeamspaceApi()
    agent = teamspace_api.create_agent(
        name="test-sdk",
        teamspace_id="ts-abc",
        base_url="test-sdk",
        api_key="test-sdk",
        model="test-sdk",
        org_id="org-abc",
    )

    assert agent.name == "test-sdk"
    assert agent.project_id == "ts-abc"
    assert agent.model == "test-sdk"


@mock.patch("lightning_sdk.api.teamspace_api._FileUploader")
def test_upload_artifact_file(uploader_mock, internal_teamspace_api_create_agent_mocker):
    teamspace_api = TeamspaceApi()
    teamspace_api.upload_artifact_file(
        local_file_path=Path("path/to/checkpoint.pt"),
        remote_dir="projects/p_id/models/m_id/version",
        cluster_id="cluster_id",
        teamspace_id="teamspace_id",
        progress_bar=False,
    )
    uploader_mock.assert_called_with(
        client=mock.ANY,
        file_path="path/to/checkpoint.pt",
        remote_path="/models/m_id/version/checkpoint.pt",
        cluster_id="cluster_id",
        teamspace_id="teamspace_id",
        progress_bar=False,
    )


def test_try_get_cluster_id(internal_teamspace_api_create_agent_mocker):
    # cluster set via env variable
    teamspace_api = TeamspaceApi()
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "cluster-via-env"}):
        cluster_id = teamspace_api._try_get_cluster_id("teamspace-id")
    assert cluster_id == "cluster-via-env"

    # teamspace has single cluster
    teamspace_api.list_clusters = mock.Mock(return_value=[mock.Mock(cluster_id="test-cluster")])
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": ""}):
        cluster_id = teamspace_api._try_get_cluster_id("teamspace-id")
    assert cluster_id == "test-cluster"

    # ambiguous, can't determine which cluster to use
    teamspace_api.list_clusters = mock.Mock(
        return_value=[
            mock.Mock(cluster_id="test-cluster-1"),
            mock.Mock(cluster_id="test-cluster-2"),
        ]
    )
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": ""}), pytest.raises(
        ValueError, match="Could not determine the current cluster id"
    ):
        _ = teamspace_api._try_get_cluster_id("teamspace-id")
