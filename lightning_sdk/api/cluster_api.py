from typing import Dict, List, Optional

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1Cluster,
    V1CloudProvider,
    V1ClusterType,
    V1ExternalCluster,
    V1ListClusterAcceleratorsResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient


class ClusterApi:
    """Internal API client for API requests to cluster endpoints."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_cluster(self, cluster_id: str, project_id: str, org_id: str) -> Externalv1Cluster:
        """Gets the cluster from given params cluster_id, project_id and owner.

        :param cluster_id: cluster ID test
        :param project_id: the project the cluster is supposed to be associated with
        :param org_id: The owning org of this cluster
        :return:
        """
        res = self._client.cluster_service_get_cluster(id=cluster_id, org_id=org_id, project_id=project_id)
        if not res:
            raise ValueError(f"Cluster {cluster_id} does not exist")
        return res

    def list_clusters(self, project_id: str) -> List[V1ExternalCluster]:
        """Lists the clusters for a given project.

        Args:
            project_id: The project to list clusters for

        Returns:
            A list of clusters
        """
        res = self._client.cluster_service_list_project_clusters(
            project_id=project_id,
        )
        return res.clusters

    def list_cluster_accelerators(self, cluster_id: str, org_id: str) -> V1ListClusterAcceleratorsResponse:
        """Lists the accelerators for a given cluster.

        :param cluster_id: cluster ID test
        :param project_id: the project the cluster is supposed to be associated with
        :param org_id: The owning org of this cluster
        """
        res = self._client.cluster_service_list_cluster_accelerators(
            id=cluster_id,
            org_id=org_id,
        )
        if not res:
            raise ValueError(f"Cluster {cluster_id} does not exist")
        return res

    def list_global_clusters(self, project_id: str, org_id: str) -> List[Externalv1Cluster]:
        """Lists the accelerators for a given project.

        :param project_id: project ID test
        :param org_id: The owning org of this project
        """
        res = self._client.cluster_service_list_clusters(
            project_id=project_id,
            org_id=org_id,
        )
        if not res:
            raise ValueError(f"Project {project_id} does not exist")
        filtered_clusters = filter(lambda x: x.spec.cluster_type == V1ClusterType.GLOBAL, res.clusters)
        return list(filtered_clusters)

    def get_cluster_provider_mapping(self, project_id: str, org_id: str) -> Dict[V1CloudProvider, str]:
        """Gets the cluster provider mapping."""
        res = self.list_global_clusters(
            project_id=project_id,
            org_id=org_id,
        )
        return {self._get_cluster_provider(cluster): cluster.id for cluster in res}

    def _get_cluster_provider(self, cluster: Optional[Externalv1Cluster]) -> V1CloudProvider:
        """Determines the cloud provider based on the cluster configuration.

        Args:
            cluster: An optional Externalv1Cluster object containing cluster specifications

        Returns:
            V1CloudProvider: The determined cloud provider, defaults to AWS if no match is found
        """
        if not cluster:
            return V1CloudProvider.AWS

        if (
            cluster.spec
            and cluster.spec.driver
            and cluster.spec.driver in [V1CloudProvider.LIGHTNING, V1CloudProvider.DGX]
        ):
            return cluster.spec.driver

        if cluster.spec:
            if cluster.spec.aws_v1:
                return V1CloudProvider.AWS
            if cluster.spec.google_cloud_v1:
                return V1CloudProvider.GCP
            if cluster.spec.lambda_labs_v1:
                return V1CloudProvider.LAMBDA_LABS
            if cluster.spec.vultr_v1:
                return V1CloudProvider.VULTR
            if cluster.spec.slurm_v1:
                return V1CloudProvider.SLURM
            if cluster.spec.voltage_park_v1:
                return V1CloudProvider.VOLTAGE_PARK
            if cluster.spec.nebius_v1:
                return V1CloudProvider.NEBIUS

        return V1CloudProvider.AWS
