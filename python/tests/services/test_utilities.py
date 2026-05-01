import re
from unittest.mock import MagicMock

import pytest

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1Cluster,
    V1AWSDirectV1,
    V1ClusterSpec,
    V1LambdaLabsDirectV1,
    V1ListClustersResponse,
    V1ListMembershipsResponse,
    V1ListProjectClusterBindingsResponse,
    V1Membership,
    V1NebiusDirectV1,
    V1ProjectClusterBinding,
)
from lightning_sdk.services.utilities import _get_cluster, _get_project


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
    assert _get_cluster(client_mock, project_id="project_id", allow_neoclouds=True).cluster_id == "1"

    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=1),
            V1ProjectClusterBinding(cluster_id="2", created_at=2),
        ]
    )
    assert _get_cluster(client_mock, project_id="project_id", allow_neoclouds=True).cluster_id == "1"

    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=2),
            V1ProjectClusterBinding(cluster_id="2", created_at=1),
        ]
    )
    assert _get_cluster(client_mock, project_id="project_id", allow_neoclouds=True).cluster_id == "2"

    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=2),
            V1ProjectClusterBinding(cluster_id="2", created_at=1),
        ]
    )
    assert _get_cluster(client_mock, project_id="project_id", cluster_id="1").cluster_id == "1"

    with pytest.raises(ValueError, match=re.escape("No valid cluster found with the provided 3.Found ['1', '2'].")):
        _get_cluster(client_mock, project_id="project_id", cluster_id="3")

    # filter out neoclouds
    client_mock.projects_service_list_project_cluster_bindings.return_value = V1ListProjectClusterBindingsResponse(
        clusters=[
            V1ProjectClusterBinding(cluster_id="1", created_at=2),
            V1ProjectClusterBinding(cluster_id="2", created_at=1),
            V1ProjectClusterBinding(cluster_id="3", created_at=3),
        ]
    )

    client_mock.cluster_service_list_clusters.return_value = V1ListClustersResponse(
        clusters=[
            Externalv1Cluster(id="1", spec=V1ClusterSpec(lambda_labs_v1=V1LambdaLabsDirectV1())),
            Externalv1Cluster(id="2", spec=V1ClusterSpec(nebius_v1=V1NebiusDirectV1())),
            Externalv1Cluster(id="3", spec=V1ClusterSpec(aws_v1=V1AWSDirectV1())),
        ]
    )

    assert _get_cluster(client_mock, project_id="project_id").cluster_id == "3"
