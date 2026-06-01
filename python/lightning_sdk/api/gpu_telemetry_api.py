from typing import Any, Optional

from lightning_sdk.lightning_cloud.rest_client import LightningClient


class GpuTelemetryApi:
    """Internal API client for source-aware GPU telemetry requests."""

    def __init__(self) -> None:
        self._client = LightningClient(max_tries=7)

    def list_gpu_telemetry(
        self,
        org_id: str,
        source_type: Optional[str] = None,
        dc: Optional[str] = None,
        cluster: Optional[str] = None,
        node: Optional[str] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List latest source-aware GPU telemetry records for an organization.

        Args:
            org_id: Owning organization ID.
            source_type: Optional telemetry source type filter.
            dc: Optional datacenter filter.
            cluster: Optional cluster filter.
            node: Optional node name filter.
            page_size: Optional maximum page size.
            page_token: Optional pagination token.

        Returns:
            Generated GPU telemetry response object.
        """
        optional_params = {
            "source_type": source_type,
            "dc": dc,
            "cluster": cluster,
            "node": node,
            "page_size": page_size,
            "page_token": page_token,
        }
        list_gpu_telemetry = getattr(self._client, "gpu_telemetry_service_list_gpu_telemetry", None)
        if list_gpu_telemetry is None:
            raise RuntimeError(
                "GPU telemetry is not available in this lightning-sdk build. "
                "Upgrade after the generated Grid GPU telemetry client is vendored."
            )

        return list_gpu_telemetry(
            org_id=org_id,
            **{key: value for key, value in optional_params.items() if value is not None},
        )
