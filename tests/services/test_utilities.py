import os
import re
from unittest.mock import MagicMock

import pytest

from lightning_sdk.lightning_cloud.openapi import (
    V1DownloadServiceExecutionArtifactResponse,
    V1ListMembershipsResponse,
    V1ListProjectClusterBindingsResponse,
    V1Membership,
    V1ProjectArtifact,
    V1ProjectClusterBinding,
)
from lightning_sdk.services import utilities as utilities_module
from lightning_sdk.services.utilities import _get_cluster, _get_project, download_file


def test_get_project():
    client_mock = MagicMock()
    client_mock.projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        memberships=[V1Membership(name="1")]
    )
    assert _get_project(client_mock).name == "1"

    client_mock.projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        memberships=[V1Membership(name="1"), V1Membership(name="2")]
    )
    assert _get_project(client_mock).name == "1"

    client_mock.projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        memberships=[V1Membership(name="1"), V1Membership(name="2")]
    )
    assert _get_project(client_mock, project_name="2").name == "2"

    client_mock.projects_service_list_memberships.return_value = V1ListMembershipsResponse(
        memberships=[V1Membership(display_name="1", name="a"), V1Membership(display_name="1", name="b")]
    )
    with pytest.raises(
        ValueError, match=re.escape("We found several teamspaces. Which one do you want to use ['a', 'b']")
    ):
        _get_project(client_mock, project_name="1")

    with pytest.raises(
        ValueError,
        match=re.escape("No valid projects found. Please reach out to lightning.ai team to create a project"),
    ):
        _get_project(client_mock, project_name="3")


def test_get_cluster():
    client_mock = MagicMock()
    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[V1ProjectClusterBinding(cluster_id="1")]
    )
    assert _get_cluster(client_mock, project_id="project_id").cluster_id == "1"

    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=1),
            V1ProjectClusterBinding(cluster_id="2", created_at=2),
        ]
    )
    assert _get_cluster(client_mock, project_id="project_id").cluster_id == "1"

    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=2),
            V1ProjectClusterBinding(cluster_id="2", created_at=1),
        ]
    )
    assert _get_cluster(client_mock, project_id="project_id").cluster_id == "2"

    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=2),
            V1ProjectClusterBinding(cluster_id="2", created_at=1),
        ]
    )
    assert _get_cluster(client_mock, project_id="project_id", cluster_id="1").cluster_id == "1"

    with pytest.raises(ValueError, match=re.escape("No valid cluster found with the provided 3.Found ['1', '2'].")):
        _get_cluster(client_mock, project_id="project_id", cluster_id="3")


def test_download_file(monkeypatch, tmpdir):
    monkeypatch.setenv("LIGHTNING_SERVICE_EXECUTION_ID", "service_id")
    monkeypatch.setenv("LIGHTNING_CLOUD_PROJECT_ID", "project_id")

    client_mock = MagicMock()
    client_mock.endpoint_service_download_service_execution_artifact.return_value = (
        V1DownloadServiceExecutionArtifactResponse(
            artifacts=[
                V1ProjectArtifact(
                    url="https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/"
                    "master/examples/pytorch/basics/autoencoder.py"
                )
            ]
        )
    )
    monkeypatch.setattr(utilities_module, "LightningClient", MagicMock(return_value=client_mock))

    filepath = "/teamspace/Uploads/a.txt"
    filepath_out = download_file(filepath, cache_dir=str(tmpdir))
    assert filepath_out == os.path.join(tmpdir, "service_id", filepath[1:])
    filepath = download_file(filepath_out, cache_dir=str(tmpdir))
    client_mock.endpoint_service_download_service_execution_artifact.assert_called_once()
