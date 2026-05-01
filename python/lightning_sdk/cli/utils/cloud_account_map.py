from lightning_sdk.api.cloud_account_api import CloudAccountApi


def cloud_account_to_display_name(cloud_account: str, teamspace_id: str) -> str:
    api = CloudAccountApi()
    cloud_accounts = api.list_global_cloud_accounts(teamspace_id=teamspace_id)
    for global_cloud_account in cloud_accounts:
        if global_cloud_account.id == cloud_account:
            return "Lightning AI"
    return cloud_account
