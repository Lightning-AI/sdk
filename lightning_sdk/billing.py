from lightning_sdk.api.billing_api import BillingApi


class Billing:
    """A class to interact with the billing API and retrieve billing-related information.

    Methods:
    -------
    get_k8s_usage(account_cloud: str)
      Retrieves Kubernetes usage information for a given cloud account.
    """

    def __init__(self) -> None:
        self._billing_api = BillingApi()

    def get_k8s_usage(self, cloud_account: str) -> float:
        """Gets the mean gpus/hour.

        Returns:
            The avaerage number of allocated gpus per hour
        """
        return self._billing_api.get_k8s_usage(cloud_account)
