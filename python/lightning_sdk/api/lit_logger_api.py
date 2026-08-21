from datetime import datetime
from typing import List, Optional

from lightning_sdk.api.utils import cached_lightning_client
from lightning_sdk.lightning_cloud.openapi import (
    V1GetLoggerMetricsResponse,
    V1MetricsStream,
)


class LitLoggerApi:
    """Internal API client for LitLogger (Experiments) requests."""

    def __init__(self) -> None:
        self._client = cached_lightning_client(retry=False)

    def list_metrics_streams(
        self,
        project_id: str,
        *,
        cloud_space_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[V1MetricsStream]:
        """List metrics streams in a teamspace."""
        kwargs: dict = {}
        if cloud_space_id is not None:
            kwargs["cloud_space_id"] = cloud_space_id
        if limit is not None:
            kwargs["limit"] = limit
        return self._client.lit_logger_service_list_metrics_streams(project_id, **kwargs).metrics_streams or []

    def get_logger_metrics(
        self,
        project_id: str,
        stream_ids: List[str],
        *,
        samples: Optional[int] = None,
        min_step: Optional[str] = None,
        max_step: Optional[str] = None,
        min_walltime: Optional[datetime] = None,
        max_walltime: Optional[datetime] = None,
    ) -> V1GetLoggerMetricsResponse:
        """Fetch metric values for a set of streams."""
        kwargs: dict = {"ids": stream_ids}
        if samples is not None:
            kwargs["samples"] = samples
        if min_step is not None:
            kwargs["min_step"] = min_step
        if max_step is not None:
            kwargs["max_step"] = max_step
        if min_walltime is not None:
            kwargs["min_walltime"] = min_walltime
        if max_walltime is not None:
            kwargs["max_walltime"] = max_walltime
        return self._client.lit_logger_service_get_logger_metrics(project_id, **kwargs)
