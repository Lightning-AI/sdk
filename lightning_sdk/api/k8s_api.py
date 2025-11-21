import json
import logging
from typing import Any, Dict, TypedDict, Union

import pandas as pd

from lightning_sdk.api.utils import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient

logger = logging.getLogger(__name__)


class K8sClusterApiError(Exception):
    """Custom exception for K8sClusterApi errors."""


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


class K8sClusterApi:
    """Internal API client for API requests to k8s endpoints."""

    def __init__(self, cloud_account: str) -> None:
        self.cloud_account = cloud_account
        self._client = LightningClient(max_tries=7)

    def _parse_request_failure_body(self, e: ApiException) -> str:
        """Parses the failure body from an ApiException.

        Args:
            e: The ApiException instance.

        Returns:
            The parsed failure body as a string.
        """
        try:
            if e.body:
                return json.loads(e.body)["message"]
            return "No additional error information provided."
        except Exception:
            return str(e.reason)

    def get_billing_usage(self, print_data: bool = False, **kwargs: Dict[str, Any]) -> Union[pd.DataFrame, pd.Series]:
        """Gets the k8s usage metrics.

        Returns:
            The k8s usage metrics as a DataFrame or Series.
        """
        try:
            response = self._client.k8_s_cluster_service_list_cluster_metrics(self.cloud_account, **kwargs)
            cluster_metrics = [entry.to_dict() for entry in response.cluster_metrics]

            df = pd.DataFrame.from_records(cluster_metrics)
            if df.empty:
                return df

            df["hour"] = pd.to_datetime(df["timestamp"]).dt.floor("h")

            # Calculate the mean of num_allocated_gpus for each hour
            aggregated = df.groupby("hour", as_index=False)["num_allocated_gpus"].mean()
            # Merge the aggregated values back into the original DataFrame
            df = df.merge(aggregated, on="hour", suffixes=("", "_mean"))

            # Replace the original num_allocated_gpus with the mean values
            df["num_allocated_gpus"] = df["num_allocated_gpus_mean"]

            # We group the data by hour and take the first occurrence to avoid duplicates
            df = df.drop_duplicates(subset="hour", keep="first")

            # Convert timestamp to hourly floor and rename columns
            df["billed_gpus"] = df.apply(_calculate_billed_k8s_gpus, axis=1)

            # Keep only the required columns
            df = df[["hour", "num_gpus", "num_requested_gpus", "num_allocated_gpus", "billed_gpus"]]
            if print_data:
                with pd.option_context("display.max_rows", None, "display.max_columns", None):
                    print(df)
            return df
        except ApiException as e:
            msg = self._parse_request_failure_body(e)
            logger.error(f"Failed to retrieve Kubernetes usage data: {msg}")
            raise K8sClusterApiError(msg) from e
