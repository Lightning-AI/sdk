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
    from lightning_sdk.teamspace import ConnectionType


class CloudAccountApi:
    """Internal API client for API requests to cluster endpoints."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_cloud_account(self, cloud_account_id: str, teamspace_id: str, org_id: str) -> Externalv1Cluster:
        """Return a cloud account by ID.

        Args:
            cloud_account_id: The cloud account ID to fetch.
            teamspace_id: The teamspace the cloud account is associated with.
            org_id: The owning organisation of the teamspace.

        Returns:
            Externalv1Cluster: The matching cloud account.

        Raises:
            ValueError: If no cloud account with the given ID exists.
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
        """Return the cloud account object by ID without requiring an org ID, or None if not found.

        Args:
            teamspace_id: The teamspace whose cloud accounts to search.
            cloud_account_id: The cloud account ID to look up.

        Returns:
            Optional[V1ExternalCluster]: The matching cloud account, or ``None`` if not found.
        """
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
        """List the accelerators available on a cloud account.

        Args:
            teamspace_id: The teamspace to query within.
            cloud_account_id: The cloud account ID whose accelerators to list.
            org_id: The owning organisation of the teamspace.

        Returns:
            Union[V1ListClusterAcceleratorsResponse, V1ListDefaultClusterAcceleratorsResponse]:
            The accelerator list response.

        Raises:
            ValueError: If the cloud account is not found or has no accelerators.
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
            res = self._list_default_cluster_accelerators(teamspace_id=teamspace_id, cloud_provider=str(cloud_provider))
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
        """Fetch the default accelerator list for a given provider.

        Args:
            teamspace_id: The teamspace used as context for the request.
            cloud_provider: The cloud provider to query accelerators for.

        Returns:
            V1ListDefaultClusterAcceleratorsResponse: The default accelerators response.
        """
        return self._client.cluster_service_list_default_cluster_accelerators(
            project_id=teamspace_id, cloud_provider=self.cloud_provider_to_v1_cloud_provider(cloud_provider)
        )

    @lru_cache(maxsize=None)  # noqa: B019
    def list_global_cloud_accounts(self, teamspace_id: str) -> List[V1ExternalCluster]:
        """List the global (non-organisation-specific) cloud accounts for a teamspace.

        Args:
            teamspace_id: The teamspace whose global cloud accounts to list.

        Returns:
            List[V1ExternalCluster]: Cloud accounts of type ``GLOBAL`` excluding aggregate providers.

        Raises:
            ValueError: If no cloud accounts are associated with the teamspace.
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

    def get_cloud_account_provider_mapping(self, teamspace_id: str) -> Dict["CloudProvider", V1ExternalCluster]:
        """Return a mapping from cloud provider to the corresponding cloud account.

        Args:
            teamspace_id: The teamspace whose cloud accounts to map.

        Returns:
            Dict[CloudProvider, V1ExternalCluster]: Provider → cloud account mapping.
        """
        res = self.list_cloud_accounts(teamspace_id=teamspace_id)
        cloud_accounts = {cloud_account.id: cloud_account for cloud_account in res}
        providers = {cloud_account.id: self._get_cloud_account_provider(cloud_account) for cloud_account in res}

        mapping = {}
        for cloud_account_id, provider in providers.items():
            if provider is not None:
                mapping[provider] = cloud_accounts[cloud_account_id]
        return mapping

    @staticmethod
    def _get_cloud_account_provider(cloud_account: Optional[V1ExternalCluster]) -> Optional["CloudProvider"]:
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
                return CloudProvider.LIGHTNING_AGGREGATE

            if cloud_account.spec.driver == V1CloudProvider.DGX:
                return CloudProvider.DGX

        if cloud_account.spec:
            if cloud_account.spec.aws_v1:
                return CloudProvider.AWS
            if cloud_account.spec.google_cloud_v1:
                return CloudProvider.GCP
            if cloud_account.spec.lambda_labs_v1:
                return CloudProvider.LAMBDA_LABS
            if cloud_account.spec.voltage_park_v1:
                return CloudProvider.VOLTAGE_PARK
            if cloud_account.spec.nebius_v1:
                return CloudProvider.NEBIUS
            if cloud_account.spec.machine_v1:
                return CloudProvider.LIGHTNING
        return None

    def resolve_cloud_account(
        self,
        teamspace_id: str,
        cloud_account: Optional[str],
        cloud_provider: Optional[Union["CloudProvider", str]],
        default_cloud_account: Optional[str],
    ) -> Optional[str]:
        """Resolve the best cloud account ID from the combination of explicit account, provider, and default.

        Priority: explicit ``cloud_account`` > provider mapping > ``default_cloud_account`` > None.

        Args:
            teamspace_id: The teamspace to resolve cloud accounts within.
            cloud_account: An explicit cloud account ID, if provided.
            cloud_provider: A preferred provider; used to find the matching account when no explicit ID is given.
            default_cloud_account: Fallback account ID when neither explicit account nor provider resolves.

        Returns:
            str | None: The resolved cloud account ID, or None if none can be determined.

        Raises:
            RuntimeError: If both ``cloud_account`` and ``cloud_provider`` are given but do not agree.
        """
        from lightning_sdk.machine import CloudProvider

        if cloud_provider and not isinstance(cloud_provider, CloudProvider):
            cloud_provider = CloudProvider(cloud_provider)

        if cloud_account:
            if cloud_provider:
                cloud_account_resp = self.get_cloud_account_non_org(teamspace_id, cloud_account)
                cloud_provider_resp = self._get_cloud_account_provider(cloud_account_resp)
                if cloud_provider_resp != cloud_provider:
                    raise RuntimeError(
                        f"Specified both cloud_provider ({cloud_provider}) and cloud_account ({cloud_account} "
                        f"has cloud provider {cloud_provider_resp}) which don't match!"
                    )

            return cloud_account

        if cloud_provider:
            cloud_account_mapping = self.get_cloud_account_provider_mapping(teamspace_id=teamspace_id)
            if cloud_provider and cloud_provider in cloud_account_mapping:
                return cloud_account_mapping[cloud_provider].id

        if default_cloud_account:
            return default_cloud_account

        return None

    @staticmethod
    def get_cloud_provider_for_connection_type(connection_type: "ConnectionType") -> "CloudProvider":
        """Return the cloud provider required for a given connection type.

        Args:
            connection_type: The connection type to look up.

        Returns:
            CloudProvider: The cloud provider associated with the given connection type.

        Raises:
            ValueError: If the connection type is not currently supported.
        """
        from lightning_sdk.machine import CloudProvider
        from lightning_sdk.teamspace import ConnectionType

        if connection_type == ConnectionType.EFS:
            return CloudProvider.AWS

        raise ValueError(f"ConnectionType {ConnectionType} currently not supported!")

    @staticmethod
    def cloud_provider_to_v1_cloud_provider(cloud_provider: Union[str, "CloudProvider"]) -> str:
        """Convert a ``CloudProvider`` enum or string to the corresponding V1 API string value.

        Args:
            cloud_provider: A ``CloudProvider`` enum member or its string representation.

        Returns:
            str: The V1 API cloud-provider string.

        Raises:
            ValueError: If the cloud provider is not supported.
        """
        from lightning_sdk.machine import CloudProvider

        if isinstance(cloud_provider, str):
            cloud_provider = CloudProvider.from_str(cloud_provider)

        if cloud_provider in (
            CloudProvider.AWS,
            CloudProvider.GCP,
            CloudProvider.DGX,
            CloudProvider.LAMBDA_LABS,
            CloudProvider.NEBIUS,
            CloudProvider.LIGHTNING_AGGREGATE,
            CloudProvider.VOLTAGE_PARK,
        ):
            return getattr(V1CloudProvider, str(cloud_provider))

        if cloud_provider == CloudProvider.LIGHTNING:
            return V1CloudProvider.MACHINE

        raise ValueError(f"Provided unsupported cloud provider {cloud_provider}")
