from typing import Any, Dict, TypedDict, Union

import pandas as pd

from lightning_sdk.lightning_cloud.rest_client import LightningClient


class RowData(TypedDict):
    num_allocated_gpus: int
    num_requested_gpus: int
    num_gpus: int


def _calculate_billed_k8s_gpus(row: RowData) -> int:
    """Calculate the number of GPUs to be billed based on the given row data.

    The function determines the billed GPUs using the following logic:
    1. If the number of allocated GPUs (`num_allocated_gpus`) is greater than 0,
       it returns the allocated GPUs.
    2. If the number of requested GPUs (`num_requested_gpus`) exceeds the available GPUs (`num_gpus`),
       it returns the available GPUs.
    3. Otherwise, it returns the number of requested GPUs.

    Returns:
        int: The number of GPUs to be billed.
    """
    if row["num_allocated_gpus"] > 0:
        return row["num_allocated_gpus"]  # Use allocated GPUs if available
    if row["num_requested_gpus"] > row["num_gpus"]:
        return row["num_gpus"]  # Use available GPUs if requested exceeds available
    return row["num_requested_gpus"]  # Otherwise, use requested GPUs


class BillingApi:
    """Internal API client for API requests to billing endpoints."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def get_k8s_usage(
        self, cluster_id: str, print_data: bool = False, **kwargs: Dict[str, Any]
    ) -> Union[pd.DataFrame, pd.Series]:
        """Gets the mean gpus/hour.

        Returns:
            The avaerage number of allocated gpus per hour
        """
        response = self._client.k8_s_cluster_service_list_cluster_metrics(cluster_id, **kwargs)
        cluster_metrics = [entry.to_dict() for entry in response.cluster_metrics]

        df = pd.DataFrame.from_records(cluster_metrics)
        if df.empty:
            return df
        # new cell
        # Average num_allocated_gpus per hour

        # Convert timestamp to hourly floor and rename columns
        df["hour"] = df["timestamp"].dt.floor("h")
        df["billed_gpus"] = df.apply(_calculate_billed_k8s_gpus, axis=1)

        # Keep only the required columns
        df = df[["hour", "num_gpus", "num_requested_gpus", "num_allocated_gpus", "billed_gpus"]]
        if print_data:
            with pd.option_context("display.max_rows", None, "display.max_columns", None):
                print(df)
        # Sum all hourly averages
        return df
