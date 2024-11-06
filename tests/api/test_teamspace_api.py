import pytest
import os
from unittest import mock
from pathlib import Path

from lightning_sdk.api.teamspace_api import TeamspaceApi
from lightning_sdk.lightning_cloud.openapi import V1Project, V1ProjectClusterBinding, V1CloudSpace, ProjectIdModelsBody, \
    ModelIdVersionsBody


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


@mock.patch("lightning_sdk.api.teamspace_api._ModelFileUploader")
def test_upload_model_file(uploader_mock):
    teamspace_api = TeamspaceApi()
    teamspace_api.upload_model_file(
        model_id="test-model-id",
        version="latest",
        local_path=Path("path/to/checkpoint.pt"),
        remote_path="modelpath/on/cluster",
        cluster_id="test-cluster-id",
        teamspace_id="test-project-id",
        progress_bar=False,
    )
    uploader_mock.assert_called_with(
        client=mock.ANY,
        model_id="test-model-id",
        version="latest",
        file_path="path/to/checkpoint.pt",
        remote_path="modelpath/on/cluster",
        cluster_id="test-cluster-id",
        teamspace_id="test-project-id",
        progress_bar=False,
    )
    uploader_mock().assert_called_with()  # .__call__()


def test_try_get_cluster_id():
    # cluster set via env variable
    teamspace_api = TeamspaceApi()
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": "cluster-via-env"}):
        cluster_id = teamspace_api._determine_cluster_id("teamspace-id")
    assert cluster_id == "cluster-via-env"

    # teamspace has single cluster
    teamspace_api.list_clusters = mock.Mock(return_value=[mock.Mock(cluster_id="test-cluster")])
    teamspace_api.get_default_cluster_id = mock.Mock(return_value="test-cluster")
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": ""}):
        cluster_id = teamspace_api._determine_cluster_id("teamspace-id")
    assert cluster_id == "test-cluster"

    # disabled cluster default
    teamspace_api.get_default_cluster_id = mock.Mock(return_value="")

    # ambiguous, can't determine which cluster to use
    teamspace_api.list_clusters = mock.Mock(
        return_value=[
            mock.Mock(cluster_id="test-cluster-1"),
            mock.Mock(cluster_id="test-cluster-2"),
        ]
    )
    with mock.patch.dict(os.environ, {"LIGHTNING_CLUSTER_ID": ""}), pytest.raises(
        RuntimeError, match="Could not determine the current cluster id"
    ):
        _ = teamspace_api._determine_cluster_id("teamspace-id")


def test_create_delete_model():
    teamspace_api = TeamspaceApi()
    # create a content reused in following cases
    model_body = dict(name="model-name",
        metadata= {},
        private=True,
        cluster_id="cluster-abc")
    # mock the models_store_list_models and models_store_create_model for empty state
    teamspace_api._models = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[])),
        models_store_create_model=mock.MagicMock(return_value=mock.MagicMock(model_id="model-id")),
    )
    teamspace_api.create_model(
        teamspace_id="ts-abc", **model_body
    )
    # validate the calls
    teamspace_api._models.models_store_list_models.assert_called_with(
        project_id="ts-abc", name="model-name")
    teamspace_api._models.models_store_create_model.assert_called_with(
        body=ProjectIdModelsBody(**model_body), project_id="ts-abc")

    # mock the models_store_list_models and models_store_create_model for non-empty state
    teamspace_api._models = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[mock.MagicMock(id="model-id")])),
        models_store_delete_model=mock.MagicMock(),
    )
    # delete the model calls
    teamspace_api.delete_model(name="model-name", version="", teamspace_id="ts-abc")
    teamspace_api._models.models_store_list_models.assert_called_with(project_id="ts-abc", name="model-name")
    teamspace_api._models.models_store_delete_model.assert_called_with(project_id="ts-abc", model_id="model-id")


def test_create_delete_model_version():
    teamspace_api = TeamspaceApi()
    model_body = dict(name="model-name",
        metadata= {},
        private=True,
        cluster_id="cluster-abc")
    # mock the models_store_list_models and models_store_create_model_version for existing model
    teamspace_api._models = mock.MagicMock(
        models_store_list_models=mock.MagicMock(return_value=mock.MagicMock(models=[mock.MagicMock(id="model-id")])),
        models_store_create_model_version=mock.MagicMock(return_value=mock.MagicMock(model_id="model-id", version="v1")),
    )
    version = teamspace_api.create_model(
        teamspace_id="ts-abc", **model_body
    )
    teamspace_api._models.models_store_list_models.assert_called_with(
        project_id="ts-abc", name="model-name")
    teamspace_api._models.models_store_create_model_version.assert_called_with(
        project_id="ts-abc", body=ModelIdVersionsBody(cluster_id= "cluster-abc"), model_id="model-id")

    teamspace_api._models = mock.MagicMock(
        models_store_list_models=mock.MagicMock(
            return_value=mock.MagicMock(models=[mock.MagicMock(id="model-id", latest_version="v1")])),
    )
    teamspace_api.delete_model(name="model-name", version="latest", teamspace_id="ts-abc")
    teamspace_api._models.models_store_delete_model_version.assert_called_with(
        project_id="ts-abc", model_id="model-id", version=version.version)
    teamspace_api.delete_model(name="model-name", version=version.version, teamspace_id="ts-abc")
    teamspace_api._models.models_store_delete_model_version.assert_called_with(
        project_id="ts-abc", model_id="model-id", version=version.version)
