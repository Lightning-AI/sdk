from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

from lightning_sdk.api.k8s_api import K8sClusterApi
from lightning_sdk.api.utils import to_iso_z


@dataclass
class HourlyUsage:
    time: datetime
    available_gpus: int
    billed_gpus: int


@dataclass
class K8sUsageResponse:
    hours: List[HourlyUsage]
    total_usage: float


class K8sCluster:
    """A class to interact with the k8s API and retrieve usage-related information.

    Methods:
    -------
    get_k8s_usage(account_cloud: str)
      Retrieves Kubernetes usage information for a given cloud account.
    """

    def __init__(self, cloud_account: str) -> None:
        self._cloud_account = cloud_account
        self._k8s_cluster = K8sClusterApi(cloud_account=cloud_account)

    def _convert_to_k8s_usage_response(self, df: pd.DataFrame) -> K8sUsageResponse:
        """Converts a DataFrame to K8sUsageResponse.

        Args:
            df (pd.DataFrame): The DataFrame containing GPU usage data.

        Returns:
            K8sUsageResponse: The converted response containing hourly usage and total usage.
        """
        if df.empty:
            return K8sUsageResponse(hours=[], total_usage=0.0)
        # Convert each row of the DataFrame to HourlyUsage
        hourly_usage_list: List[HourlyUsage] = [
            HourlyUsage(time=row["hour"], available_gpus=row["num_gpus"], billed_gpus=row["billed_gpus"])
            for _, row in df.iterrows()
        ]

        # Calculate total usage (sum of billed GPUs)
        total_usage = df["billed_gpus"].sum()

        # Create and return the K8sUsageResponse
        return K8sUsageResponse(hours=hourly_usage_list, total_usage=total_usage)

    def get_billing_usage(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        print_data: bool = False,
    ) -> K8sUsageResponse:
        """Gets the k8s usage metrics.

        Args:
            cloud_account: The cloud account to get usage for
            start_date: The UTC start date for the usage period (optional)
            end_date: The UTC end date for the usage period (optional)

        Returns:
            K8sUsageResponse: The Kubernetes usage response containing hourly usage and total usage.
        """
        k8s_args = {}
        if start_date is not None:
            k8s_args["start"] = to_iso_z(start_date)
        if end_date is not None:
            k8s_args["end"] = to_iso_z(end_date)
        return self._convert_to_k8s_usage_response(
            self._k8s_cluster.get_billing_usage(print_data=print_data, **k8s_args)
        )
