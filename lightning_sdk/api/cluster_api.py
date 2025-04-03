from lightning_sdk.lightning_cloud.openapi import Externalv1Cluster
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
