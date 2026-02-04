import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, TypedDict

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

    def get_billing_usage(self, print_data: bool = False, **kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gets the k8s usage metrics.

        Returns:
            The k8s usage metrics as a list of dictionaries.
        """
        try:
            response = self._client.k8_s_cluster_service_list_cluster_metrics(self.cloud_account, **kwargs)
            cluster_metrics = [entry.to_dict() for entry in response.cluster_metrics]

            if not cluster_metrics:
                return []

            # Parse timestamps and floor to hour, then group by hour
            hourly_data = defaultdict(lambda: {"allocated_gpus": [], "first_entry": None})

            for entry in cluster_metrics:
                # Parse timestamp and floor to hour
                timestamp = entry["timestamp"]
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                hour = timestamp.replace(minute=0, second=0, microsecond=0)

                # allocated GPUs cannot exceed total number of gpus
                num_gpus = entry["num_gpus"]
                allocated_gpus = entry["num_allocated_gpus"]
                if allocated_gpus > num_gpus:
                    allocated_gpus = entry["num_requested_gpus"]

                # Store allocated GPUs for averaging
                hourly_data[hour]["allocated_gpus"].append(allocated_gpus)

                # Keep first entry for each hour (for other fields)
                if hourly_data[hour]["first_entry"] is None:
                    hourly_data[hour]["first_entry"] = entry

            # Build result list with aggregated data
            result = []
            for hour, data in sorted(hourly_data.items()):
                entry = data["first_entry"]

                # Calculate mean of allocated GPUs for this hour
                mean_allocated_gpus = sum(data["allocated_gpus"]) / len(data["allocated_gpus"])

                # Create row with mean allocated GPUs
                row = {
                    "hour": hour,
                    "num_gpus": entry["num_gpus"],
                    "num_requested_gpus": entry["num_requested_gpus"],
                    "num_allocated_gpus": mean_allocated_gpus,
                }

                # Calculate billed GPUs
                row["billed_gpus"] = _calculate_billed_k8s_gpus(
                    {
                        "num_allocated_gpus": mean_allocated_gpus,
                        "num_requested_gpus": row["num_requested_gpus"],
                        "num_gpus": row["num_gpus"],
                    }
                )

                result.append(row)

            if print_data:
                # Print using rich table (local import)
                from rich.console import Console
                from rich.table import Table

                table = Table(title="K8s Billing Usage")
                table.add_column("Hour", style="cyan")
                table.add_column("Available GPUs", justify="right", style="green")
                table.add_column("Requested GPUs", justify="right", style="yellow")
                table.add_column("Allocated GPUs (Avg)", justify="right", style="magenta")
                table.add_column("Billed GPUs", justify="right", style="red")

                for row in result:
                    table.add_row(
                        str(row["hour"]),
                        str(row["num_gpus"]),
                        str(row["num_requested_gpus"]),
                        f"{row['num_allocated_gpus']:.2f}",
                        str(row["billed_gpus"]),
                    )

                console = Console()
                console.print(table)

            return result
        except ApiException as e:
            msg = self._parse_request_failure_body(e)
            logger.error(f"Failed to retrieve Kubernetes usage data: {msg}")
            raise K8sClusterApiError(msg) from e
