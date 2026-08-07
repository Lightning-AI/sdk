from typing import List

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.lightning_cloud.openapi import V1ExternalCluster


def cloud_account_display_name_from_list(cloud_account: str, global_cloud_accounts: List[V1ExternalCluster]) -> str:
    """Resolve a display name from an already-fetched list of global cloud accounts.

    Use this instead of ``cloud_account_to_display_name`` when resolving names for many cloud
    accounts in a loop (e.g. one row per Studio/Job) to avoid refetching the same list every time.
    """
    for global_cloud_account in global_cloud_accounts:
        if global_cloud_account.id == cloud_account:
            return "Lightning AI"
    return cloud_account


def cloud_account_to_display_name(cloud_account: str, teamspace_id: str) -> str:
    api = CloudAccountApi()
    cloud_accounts = api.list_global_cloud_accounts(teamspace_id=teamspace_id)
    return cloud_account_display_name_from_list(cloud_account, cloud_accounts)
