from datetime import datetime
from typing import Optional

from lightning_sdk.api.billing_api import BillingApi
from lightning_sdk.api.utils import to_iso_z


class Billing:
    """A class to interact with the billing API and retrieve billing-related information.

    Methods:
    -------
    get_k8s_usage(account_cloud: str)
      Retrieves Kubernetes usage information for a given cloud account.
    """

    def __init__(self) -> None:
        self._billing_api = BillingApi()

    def get_k8s_usage(
        self, cloud_account: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> float:
        """Gets the mean gpus/hour.

        Args:
            cloud_account: The cloud account to get usage for
            start_date: The UTC start date for the usage period (optional)
            end_date: The UTC end date for the usage period (optional)

        Returns:
            The avaerage number of allocated gpus per hour
        """
        k8s_args = {}
        if start_date is not None:
            k8s_args["start"] = to_iso_z(start_date)
        if end_date is not None:
            k8s_args["end"] = to_iso_z(end_date)
        return self._billing_api.get_k8s_usage(cloud_account, **k8s_args)
