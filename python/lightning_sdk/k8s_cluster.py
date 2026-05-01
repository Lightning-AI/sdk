from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from lightning_sdk.api.k8s_api import K8sClusterApi
from lightning_sdk.api.utils import to_iso_z


@dataclass
class HourlyUsage:
    """GPU billing data for a single one-hour window.

    Attributes:
        time: Start of the hour (UTC).
        available_gpus: Total GPUs allocated during this hour.
        billed_gpus: GPUs that were actively billed during this hour.
    """

    time: datetime
    available_gpus: int
    billed_gpus: int


@dataclass
class K8sUsageResponse:
    """Aggregated GPU billing response for a queried time range.

    Attributes:
        hours: Per-hour breakdown of GPU usage.
        total_usage: Sum of billed GPUs across all hours.
    """

    hours: List[HourlyUsage]
    total_usage: float


class K8sCluster:
    """Interact with a Kubernetes cluster to retrieve GPU billing usage."""

    def __init__(self, cloud_account: str) -> None:
        """Connect to a Kubernetes cluster by cloud account.

        Args:
            cloud_account: The cloud account ID associated with the cluster.
        """
        self._cloud_account = cloud_account
        self._k8s_cluster = K8sClusterApi(cloud_account=cloud_account)

    def _convert_to_k8s_usage_response(self, data: List[Dict[str, Any]]) -> K8sUsageResponse:
        """Converts a list of usage data to K8sUsageResponse.

        Args:
            data (List[Dict[str, Any]]): The list of dictionaries containing GPU usage data.

        Returns:
            K8sUsageResponse: The converted response containing hourly usage and total usage.
        """
        if not data:
            return K8sUsageResponse(hours=[], total_usage=0.0)

        # Convert each row to HourlyUsage
        hourly_usage_list: List[HourlyUsage] = [
            HourlyUsage(time=row["hour"], available_gpus=row["num_gpus"], billed_gpus=row["billed_gpus"])
            for row in data
        ]

        # Calculate total usage (sum of billed GPUs)
        total_usage = sum(row["billed_gpus"] for row in data)

        # Create and return the K8sUsageResponse
        return K8sUsageResponse(hours=hourly_usage_list, total_usage=total_usage)

    def get_billing_usage(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        print_data: bool = False,
    ) -> K8sUsageResponse:
        """Retrieve GPU billing usage for this cluster.

        Args:
            start_date: UTC start of the query window. Defaults to None (no lower bound).
            end_date: UTC end of the query window. Defaults to None (no upper bound).
            print_data: Whether to print the raw usage data to stdout. Defaults to False.

        Returns:
            K8sUsageResponse: Hourly GPU usage breakdown and the total billed GPU count.
        """
        k8s_args = {}
        if start_date is not None:
            k8s_args["start"] = to_iso_z(start_date)
        if end_date is not None:
            k8s_args["end"] = to_iso_z(end_date)
        return self._convert_to_k8s_usage_response(
            self._k8s_cluster.get_billing_usage(print_data=print_data, **k8s_args)
        )
