from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from lightning_sdk.lightning_cloud.openapi import (
    Externalv1Cluster,
    V1CloudProvider,
    V1ClusterType,
    V1ExternalCluster,
    V1ListClusterAcceleratorsResponse,
    V1ListDefaultClusterAcceleratorsResponse,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient

if TYPE_CHECKING:
    from lightning_sdk.machine import CloudProvider


class CloudAccountApi:
    """Internal API client for API requests to cluster endpoints."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_cloud_account(self, cloud_account_id: str, teamspace_id: str, org_id: str) -> Externalv1Cluster:
        """Gets the cluster from given params cluster_id, project_id and owner.

        Args:
            cloud_account_id: the cloud account to get
            teamspace_id: the teamspace the cloud_account is supposed to be associated with
            org_id: The owning org of this teamspace

        """
        res = self._client.cluster_service_get_cluster(id=cloud_account_id, org_id=org_id, project_id=teamspace_id)
        if not res:
            raise ValueError(f"CloudAccount {cloud_account_id} does not exist")
        return res

    @lru_cache(maxsize=None)  # noqa: B019
    def list_cloud_accounts(self, teamspace_id: str) -> List[V1ExternalCluster]:
        """Lists the cloud accounts for a given teamspace.

        Args:
            teamspace_id: The teamspace to list cloud accounts for

        Returns:
            A list of cloud accounts
        """
        res_project = self._client.cluster_service_list_project_clusters(
            project_id=teamspace_id,
        )
        res_global = self._client.cluster_service_list_clusters(
            project_id=teamspace_id,
        )

        # can't use set here because the cloud_accounts are not hashable
        cloud_accounts = []
        cloud_account_ids = []
        for cloud_account in res_project.clusters + res_global.clusters:
            if cloud_account.id not in cloud_account_ids:
                cloud_accounts.append(cloud_account)
                cloud_account_ids.append(cloud_account.id)

        return cloud_accounts

    def get_cloud_account_non_org(self, teamspace_id: str, cloud_account_id: str) -> Optional[V1ExternalCluster]:
        for cluster in self.list_cloud_accounts(teamspace_id=teamspace_id):
            if cluster.id == cloud_account_id:
                return cluster

        return None

    @lru_cache(maxsize=None)  # noqa: B019
    def list_cloud_account_accelerators(
        self,
        teamspace_id: str,
        cloud_account_id: str,
        org_id: str,
    ) -> Union[V1ListClusterAcceleratorsResponse, V1ListDefaultClusterAcceleratorsResponse]:
        """Lists the accelerators for a given cloud account.

        Args:
            cloud_account_id: cluster ID to list accelerators for
        """
        # map cloud_account to provider
        cloud_provider = None
        is_default = True
        for cloud_account in self.list_cloud_accounts(teamspace_id=teamspace_id):
            if cloud_account.id == cloud_account_id:
                is_default = cloud_account.spec.cluster_type == V1ClusterType.GLOBAL
                cloud_provider = self._get_cloud_account_provider(cloud_account)
                break

        if cloud_provider is None:
            raise ValueError(
                f"Cloud Account {cloud_account_id} is not a default cloud account. Are you in the correct teamspace?"
            )

        if is_default:
            res = self._list_default_cluster_accelerators(teamspace_id=teamspace_id, cloud_provider=cloud_provider)
        else:
            res = self._client.cluster_service_list_cluster_accelerators(
                id=cloud_account_id,
                org_id=org_id,
            )

        if not res:
            raise ValueError(f"CloudAccount {cloud_account_id} does not exist")
        return res

    def _list_default_cluster_accelerators(
        self, teamspace_id: str, cloud_provider: Union[str, "CloudProvider"]
    ) -> V1ListDefaultClusterAcceleratorsResponse:
        return self._client.cluster_service_list_default_cluster_accelerators(
            project_id=teamspace_id, cloud_provider=str(cloud_provider)
        )

    @lru_cache(maxsize=None)  # noqa: B019
    def list_global_cloud_accounts(self, teamspace_id: str) -> List[V1ExternalCluster]:
        """Lists the accelerators for a given teamspace.

        Args:
            teamspace_id: id of the teamspace to get the associated cloud_accounts for
        """
        cloud_accounts = self.list_cloud_accounts(teamspace_id=teamspace_id)
        if not cloud_accounts:
            raise ValueError(f"Teamspace {teamspace_id} does not exist")
        filtered_cloud_accounts = filter(lambda x: x.spec.cluster_type == V1ClusterType.GLOBAL, cloud_accounts)
        # TODO: remove aggregate filter once finished
        filtered_cloud_accounts = filter(
            lambda x: x.spec.driver != V1CloudProvider.LIGHTNING_AGGREGATE, filtered_cloud_accounts
        )
        return list(filtered_cloud_accounts)

    def get_cloud_account_provider_mapping(self, teamspace_id: str) -> Dict["CloudProvider", str]:
        """Gets the cloud account <-> provider mapping."""
        res = self.list_global_cloud_accounts(teamspace_id=teamspace_id)
        return {self._get_cloud_account_provider(cloud_account): cloud_account.id for cloud_account in res}

    @staticmethod
    def _get_cloud_account_provider(cloud_account: Optional[V1ExternalCluster]) -> "CloudProvider":
        """Determines the cloud provider based on the cloud_account configuration.

        Args:
            cloud_account: An optional Externalv1Cluster object containing cluster specifications

        Returns:
            CloudProvider: The determined cloud provider, defaults to AWS if no match is found
        """
        from lightning_sdk.machine import CloudProvider

        if not cloud_account:
            return CloudProvider.AWS

        if cloud_account.spec and cloud_account.spec.driver:
            if cloud_account.spec.driver == V1CloudProvider.LIGHTNING:
                return CloudProvider.LIGHTNING

            if cloud_account.spec.driver == V1CloudProvider.DGX:
                return CloudProvider.DGX

        if cloud_account.spec:
            if cloud_account.spec.aws_v1:
                return CloudProvider.AWS
            if cloud_account.spec.google_cloud_v1:
                return CloudProvider.GCP
            if cloud_account.spec.lambda_labs_v1:
                return CloudProvider.LAMBDA_LABS
            if cloud_account.spec.vultr_v1:
                return CloudProvider.VULTR
            if cloud_account.spec.voltage_park_v1:
                return CloudProvider.VOLTAGE_PARK
            if cloud_account.spec.nebius_v1:
                return CloudProvider.NEBIUS

        return CloudProvider.AWS

    def resolve_cloud_account(
        self,
        teamspace_id: str,
        cloud_account: Optional[str],
        cloud_provider: Optional[Union["CloudProvider", str]],
        default_cloud_account: Optional[str],
    ) -> Optional[str]:
        from lightning_sdk.machine import CloudProvider

        if cloud_provider and not isinstance(cloud_provider, CloudProvider):
            cloud_provider = CloudProvider(cloud_provider)

        if cloud_account:
            if cloud_provider:
                cloud_account_resp = self.get_cloud_account_non_org(teamspace_id, cloud_account)
                cloud_provider_resp = self._get_cloud_account_provider(cloud_account_resp)
                if cloud_provider_resp != cloud_provider:
                    raise RuntimeError(
                        f"Specified both cloud_provider ({cloud_provider}) and "
                        "cloud_account ({cloud_account} has cloud provider {cloud_provider_resp}) which don't match!"
                    )

            return cloud_account

        if cloud_provider:
            cloud_account_mapping = self.get_cloud_account_provider_mapping(teamspace_id=teamspace_id)
            if cloud_provider and cloud_provider in cloud_account_mapping:
                return cloud_account_mapping[cloud_provider]

        if default_cloud_account:
            return default_cloud_account

        return None
