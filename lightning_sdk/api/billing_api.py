from typing import Any, Dict

import pandas as pd

from lightning_sdk.lightning_cloud.rest_client import LightningClient


class BillingApi:
    """Internal API client for API requests to billing endpoints."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_k8s_usage(self, cluster_id: str, **kwargs: Dict[str, Any]) -> float:
        """Gets the mean gpus/hour.

        Returns:
            The avaerage number of allocated gpus per hour
        """
        response = self._client.k8_s_cluster_service_list_cluster_metrics(cluster_id, **kwargs)
        cluster_metrics = [entry.to_dict() for entry in response.cluster_metrics]

        df = pd.DataFrame.from_records(cluster_metrics)
        if df.empty:
            return 0.0
        # new cell
        # Average num_allocated_gpus per hour
        hourly_avg = df.groupby(df["timestamp"].dt.floor("h"))["num_allocated_gpus"].mean()

        # Sum all hourly averages
        return hourly_avg.sum()
