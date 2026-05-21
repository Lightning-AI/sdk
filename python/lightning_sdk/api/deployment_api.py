import csv
import gzip
import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from time import sleep
from typing import Any, Dict, List, Literal, Optional, Sequence, TextIO, Tuple, Union

import requests

from lightning_sdk.api import lightning_storage_upload as lightning_storage_upload_api
from lightning_sdk.api.utils import _FileUploader, _machine_to_compute_name, resolve_path_mappings
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceCreateDeploymentBody,
    V1AutoscalingSpec,
    V1AutoscalingTargetMetric,
    V1BYOMSpec,
    V1Deployment,
    V1DeploymentStrategy,
    V1Endpoint,
    V1EndpointAuth,
    V1EnvVar,
    V1HealthCheckExec,
    V1HealthCheckHttpGet,
    V1Job,
    V1JobHealthCheckConfig,
    V1JobLogsResponse,
    V1JobSpec,
    V1RollingUpdateStrategy,
    V1WeightSource,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine
from lightning_sdk.utils.filesystem import parse_lit_url

_METRICS = ["GPU", "CPU", "RPM"]
DEFAULT_REQUEST_CAPTURE_PATH = "/v1/chat/completions"
_CSV_FIELDNAMES = (
    "request_id",
    "received_at",
    "status_code",
    "method",
    "path",
    "latency_ms",
    "resource_id",
    "captured",
    "request_body_size",
    "response_body_size",
    "request_body",
    "response_body",
    "raw_content",
    "content_missing",
    "content_error",
)


DateTimeLike = Union[datetime, str]
PathLike = Union[Path, str]


@dataclass
class RequestCaptureExportResult:
    output_dir: Path
    manifest_path: Path
    csv_path: Path
    jsonl_path: Path
    row_count: int
    captured_count: int
    uncaptured_count: int
    missing_content_count: int
    content_error_count: int
    uploaded_artifacts: Optional[Dict[str, str]] = None


@dataclass
class _LightningStorageUploadTarget:
    data_connection_id: str
    cloud_account: Optional[str]
    folder_name: str
    relative_parts: Tuple[str, ...]

    def absolute_artifact_path(self, filename: str) -> str:
        parts = ("teamspace", "lightning_storage", self.folder_name, *self.relative_parts, filename)
        return "/" + "/".join(parts)

    def remote_artifact_path(self, filename: str) -> str:
        remote_path = PurePosixPath(*self.relative_parts, filename)
        return remote_path.as_posix()


class MissingRequestContentError(RuntimeError):
    pass


class Env:
    """The Env describes an environnement variable."""

    def __init__(self, name: str, value: str) -> str:
        self.name = name
        self.value = value


class Secret:
    """The Secret describes a protected environnement variable."""

    def __init__(self, name: str) -> str:
        self.name = name


class Auth:
    """The base auth class."""


class BasicAuth(Auth):
    """The BasicAuth describes the basic auth mechanism where a username and password are required to authenticate."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password


class TokenAuth(Auth):
    """The TokenAuth describes the token auth mechanism where a token is required to authenticate."""

    def __init__(self, token: str) -> None:
        self.token = token


class ApiKeyAuth(Auth):
    """The ApiKeyAuth describes that the user requires a Lightning API Key to authenticate."""


class ReleaseStrategy:
    """The base class for release strategy."""


class RollingUpdateReleaseStrategy(ReleaseStrategy):
    """The RollingUpdateReleaseStrategy describes the rolling update strategy.

    Args:
        max_surge: The max_surge argument controls the maximum number of additional replicas
            that can be created during a rolling update.
            It specifies the number above the desired replica count that can be temporarily created.
            During an update, Lightning creates new replicas to replace the old ones,
            and the max_surge argument ensures that the total number of pods does not exceed a certain limit.
        max_unavailable: The max_unavailable argument determines the maximum number of replicas that
            can be unavailable during a rolling update. It specifies the maximum number that can be simultaneously
            removed from service during the update progresses. By default, Lightning terminates one replica at a
            time while creating new replicas, ensuring that the desired replica count is maintained.

    """

    def __init__(self, max_surge: int = 1, max_unavailable: int = 0) -> None:
        self.max_surge = max_surge
        self.max_unavailable = max_unavailable


class HealthCheck:
    pass


class ExecHealthCheck(HealthCheck):
    """The ExecHealthCheck determines whether your service is ready using exec command in the container.

    Args:
        command: The command to be executed within your container to decide whether the service is ready.
        timeout_seconds: The total number of time to wait before declaring the service as unhealthy.
        initial_delay_seconds: The amount of time to wait before starting to execute the command.
        failure_threshold: The total number of retries to do befor declaring the service as unhealthy.
        interval_seconds: The amount of time between retries.

    """

    def __init__(
        self,
        command: str,
        initial_delay_seconds: int = 0,
        failure_threshold: int = 3600,
        interval_seconds: int = 1,
        timeout_seconds: int = 30,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.initial_delay_seconds = initial_delay_seconds
        self.failure_threshold = failure_threshold
        self.interval_seconds = interval_seconds


class HttpHealthCheck(HealthCheck):
    """The HttpHealthCheck determines whether your service is ready using http request.

    Args:
        path: The server path to hit to check whether the server is healthy
        port: The server port to hit to check whether the server is healthy
        timeout_seconds: The total number of time to wait before declaring the service as unhealthy.
        initial_delay_seconds: The amount of time to wait before starting to execute the command.
        failure_threshold: The total number of retries to do befor declaring the service as unhealthy.
        interval_seconds: The amount of time between retries.

    """

    def __init__(
        self,
        path: str,
        port: float,
        initial_delay_seconds: int = 0,
        failure_threshold: int = 3600,
        interval_seconds: int = 1,
        timeout_seconds: int = 30,
    ) -> None:
        self.path = path
        self.port = port
        self.initial_delay_seconds = initial_delay_seconds
        self.failure_threshold = failure_threshold
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds


class AutoScalingMetric:
    """The AutoScalingMetric determines the metric used to decide whether we should autoscale.

    Args:
        name: The name of the metric used to decide whether we should autoscale.
        target: The metric threshold  to decide whether we should autoscale.

    """

    def __init__(
        self,
        name: Literal["GPU", "CPU", "RPM"],
        target: float,
    ) -> None:
        self.name = name
        self.target = target


class AutoScaleConfig:
    """The AutoScaleConfig determines how to autoscale your deployment.

    Args:
        min_replicas: The minimum number of replicas. When set to 0, the replicas will
            stop when there is no traffic left.
        max_replicas: The maximum number of replicas.
        metric: The metric used to decide whether we should autoscale.
        threshold: The metric threshold  to decide whether we should autoscale.
        target_metrics: Multiple target metrics to autoscale the deployment.
        idle_threshold_seconds: The amount of time to wait before stopping a replica
            after the latest seen request.

    """

    def __init__(
        self,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        metric: Optional[Literal["GPU", "CPU", "RPM"]] = None,
        threshold: Optional[float] = None,
        target_metrics: Optional[List[AutoScalingMetric]] = None,
        idle_threshold_seconds: Optional[str] = None,
        scale_down_cooldown_seconds: Optional[str] = None,
        scale_up_cooldown_seconds: Optional[str] = None,
    ) -> None:
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.metric = metric
        self.threshold = threshold
        self.target_metrics = target_metrics
        self.idle_threshold_seconds = idle_threshold_seconds
        self.scale_down_cooldown_seconds = scale_down_cooldown_seconds
        self.scale_up_cooldown_seconds = scale_up_cooldown_seconds


class DeploymentApi:
    """Internal API client for Deployment requests (mainly http requests)."""

    def __init__(self, wait_on_stop: int = 5) -> None:
        self._client = LightningClient(max_tries=7)
        self._wait_on_stop = wait_on_stop

    def get_deployment_by_name(self, name: str, teamspace_id: str) -> Optional[V1Deployment]:
        """Fetch a deployment by name, returning ``None`` if it does not exist.

        Args:
            name: The name of the deployment to fetch.
            teamspace_id: The teamspace that owns the deployment.

        Returns:
            Optional[V1Deployment]: The deployment, or ``None`` if not found.

        Raises:
            ApiException: If the API returns an unexpected error.
        """
        try:
            return self._client.jobs_service_get_deployment_by_name(project_id=teamspace_id, name=name)
        except ApiException as ex:
            if "Reason: Not Found" in str(ex):
                return None
            raise ex

    def get_deployment_by_id(self, deployment_id: str, teamspace_id: str) -> Optional[V1Deployment]:
        """Fetch a deployment by its unique ID, returning ``None`` if it does not exist.

        Args:
            deployment_id: The unique ID of the deployment to fetch.
            teamspace_id: The teamspace that owns the deployment.

        Returns:
            Optional[V1Deployment]: The deployment, or ``None`` if not found.

        Raises:
            ApiException: If the API returns an unexpected error.
        """
        try:
            return self._client.jobs_service_get_deployment(project_id=teamspace_id, id=deployment_id)
        except ApiException as ex:
            if "Reason: Not Found" in str(ex):
                return None
            raise ex

    def list_deployments(
        self,
        teamspace_id: str,
        *,
        cloudspace_id: Optional[str] = None,
        user_ids: Optional[List[str]] = None,
        standalone: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: int = 100,
    ) -> List[V1Deployment]:
        """List deployments in a teamspace, following API pagination.

        Args:
            teamspace_id: The teamspace that owns the deployments.
            cloudspace_id: Optional Studio/cloudspace filter.
            user_ids: Optional user ID filter.
            standalone: Optional standalone deployment filter.
            sort_by: Optional server-side sort key.
            sort_order: Optional sort order.
            limit: Page size for each API request.

        Returns:
            List[V1Deployment]: All matching deployments.
        """
        deployments = []
        page_token = None

        while True:
            kwargs = {
                "cloudspace_id": cloudspace_id,
                "user_ids": user_ids,
                "standalone": standalone,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": limit,
            }
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            if page_token:
                kwargs["page_token"] = page_token

            response = self._client.jobs_service_list_deployments(project_id=teamspace_id, **kwargs)
            deployments.extend(response.deployments or [])

            page_token = response.next_page_token
            if not page_token:
                break

        return deployments

    def create_deployment(
        self,
        deployment: V1Deployment,
        from_onboarding: Optional[bool] = None,
        from_litserve: Optional[bool] = None,
    ) -> V1Deployment:
        """Create a deployment from a ``V1Deployment`` object and return the server-created resource.

        Args:
            deployment: The deployment configuration to create.
            from_onboarding: Flag indicating the deployment was created through the onboarding flow.
            from_litserve: Flag indicating the deployment was created from LitServe.

        Returns:
            V1Deployment: The created deployment as returned by the server.
        """
        return self._client.jobs_service_create_deployment(
            project_id=deployment.project_id,
            body=JobsServiceCreateDeploymentBody(
                cloudspace_id=deployment.cloudspace_id,
                autoscaling=deployment.autoscaling,
                cluster_id=deployment.spec.cluster_id,
                endpoint=deployment.endpoint,
                name=deployment.name,
                replicas=deployment.replicas,
                spec=deployment.spec,
                strategy=deployment.strategy,
                byom_spec=deployment.byom_spec,
                acknowledged_warnings=deployment.acknowledged_warnings,
                from_onboarding=from_onboarding,
                from_litserve=from_litserve,
            ),
        )

    def update_deployment(
        self,
        deployment: V1Deployment,
        machine: Optional[Machine] = None,
        image: Optional[str] = None,
        entrypoint: Optional[str] = None,
        command: Optional[str] = None,
        env: Optional[List[Union[Env, Secret]]] = None,
        spot: Optional[bool] = None,
        cloud_account: Optional[str] = None,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        name: Optional[str] = None,
        ports: Optional[List[float]] = None,
        release_strategy: Optional[ReleaseStrategy] = None,
        replicas: Optional[int] = None,
        health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
        auth: Optional[Union[BasicAuth, TokenAuth]] = None,
        custom_domain: Optional[str] = None,
        quantity: Optional[int] = None,
        include_credentials: Optional[bool] = None,
        max_runtime: Optional[int] = None,
        path_mappings: Optional[Dict[str, str]] = None,
    ) -> V1Deployment:
        """Apply changes to a deployment in-place and persist them via the API.

        Any change to ``image``, ``entrypoint``, ``command``, ``env``, ``health_check``,
        ``cloud_account``, ``spot``, ``quantity``, ``include_credentials``, or ``max_runtime``
        triggers a new release; a ``release_strategy`` is required in that case.

        Args:
            deployment: The deployment object to update (modified in-place).
            machine: New machine type for the deployment.
            image: New container image.
            entrypoint: New container entrypoint.
            command: New container command.
            env: New list of environment variables or secrets.
            spot: Whether to use spot instances.
            cloud_account: New cloud account ID.
            min_replicas: New minimum replica count for autoscaling.
            max_replicas: New maximum replica count for autoscaling.
            name: New deployment name.
            ports: New list of exposed ports.
            release_strategy: Release strategy required when a new release is triggered.
            replicas: New fixed replica count.
            health_check: New readiness probe configuration.
            auth: New authentication configuration.
            custom_domain: New custom domain for the endpoint.
            quantity: New quantity override for the job spec.
            include_credentials: Whether to inject credentials into the deployment.
            max_runtime: New maximum runtime in seconds.
            path_mappings: New path-to-data-connection mappings.

        Returns:
            V1Deployment: The updated deployment as returned by the server.

        Raises:
            RuntimeError: If a new release is required but no ``release_strategy`` is provided.
        """
        # Update the deployment in place

        apply_change(deployment, "name", name)
        apply_change(deployment, "replicas", replicas)
        apply_change(deployment, "strategy", to_strategy(release_strategy))

        apply_change(deployment.autoscaling, "min_replicas", min_replicas)
        apply_change(deployment.autoscaling, "max_replicas", max_replicas)
        apply_change(deployment.autoscaling, "max_replicas", max_replicas)

        # Any updates to the Job Spec triggers a new release
        if machine:
            apply_change(deployment.spec, "instance_name", _machine_to_compute_name(machine))
            apply_change(deployment.spec, "instance_type", _machine_to_compute_name(machine))

        requires_release = False
        requires_release |= apply_change(deployment.spec, "image", image)

        if path_mappings:
            requires_release |= apply_change(
                deployment.spec, "path_mappings", resolve_path_mappings(path_mappings, None, None)
            )

        requires_release |= apply_change(deployment.spec, "entrypoint", entrypoint)
        requires_release |= apply_change(deployment.spec, "command", command)
        requires_release |= apply_change(deployment.spec, "env", to_env(env))
        requires_release |= apply_change(deployment.spec, "readiness_probe", to_health_check(health_check, False))
        requires_release |= apply_change(deployment.spec, "cluster_id", cloud_account)
        requires_release |= apply_change(deployment.spec, "spot", spot)
        requires_release |= apply_change(deployment.spec, "quantity", quantity)
        requires_release |= apply_change(deployment.spec, "include_credentials", include_credentials)
        requires_release |= apply_change(
            deployment.spec, "requested_run_duration_seconds", str(max_runtime) if max_runtime is not None else None
        )

        if requires_release:
            if deployment.strategy is None:
                raise RuntimeError("When doing a new release, a release strategy needs to be defined.")

            # Force the deployment to make a new snapshot
            if deployment.spec.cloudspace_id != "" and deployment.spec.run_id != "":
                deployment.spec.run_id = ""

            print("Some core arguments have changed. We are making a new release.")

        apply_change(deployment.endpoint, "custom_domain", custom_domain)
        apply_change(deployment.endpoint, "auth", to_endpoint_auth(auth))
        apply_change(deployment.endpoint, "ports", [str(port) for port in ports] if ports else None)

        return self._client.jobs_service_update_deployment(
            project_id=deployment.project_id,
            id=deployment.id,
            body=deployment,
        )

    def delete_deployment(self, deployment: V1Deployment) -> None:
        """Delete a deployment.

        Args:
            deployment: The deployment to delete.
        """
        self._client.jobs_service_delete_deployment(project_id=deployment.project_id, id=deployment.id)

    def list_deployment_jobs(
        self,
        teamspace_id: str,
        deployment_id: str,
        *,
        state: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: int = 100,
    ) -> List[V1Job]:
        """List jobs that belong to a deployment, following API pagination.

        Args:
            teamspace_id: The teamspace that owns the deployment.
            deployment_id: The deployment ID.
            state: Optional job state filter.
            sort_by: Optional server-side sort key.
            sort_order: Optional sort order.
            limit: Page size for each API request.

        Returns:
            List[V1Job]: All matching jobs.
        """
        jobs = []
        page_token = None

        while True:
            kwargs = {
                "deployment_id": deployment_id,
                "state": state,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": limit,
            }
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            if page_token:
                kwargs["page_token"] = page_token

            response = self._client.jobs_service_list_jobs(project_id=teamspace_id, **kwargs)
            jobs.extend(response.jobs or [])

            page_token = response.next_page_token
            if not page_token:
                break

        return jobs

    def get_job_logs(
        self,
        teamspace_id: str,
        job_id: str,
        *,
        deployment_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        rank: Optional[int] = None,
    ) -> V1JobLogsResponse:
        """Get paginated log metadata for a deployment job.

        Args:
            teamspace_id: The teamspace that owns the job.
            job_id: The job ID.
            deployment_id: Optional deployment ID filter.
            since: Optional start timestamp.
            until: Optional end timestamp.
            rank: Optional distributed job rank.

        Returns:
            V1JobLogsResponse: Log page metadata and follow URL.
        """
        kwargs = {
            "deployment_id": deployment_id,
            "since": since,
            "until": until,
            "rank": rank,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return self._client.jobs_service_get_job_logs(project_id=teamspace_id, id=job_id, **kwargs)

    def stop(self, deployment: V1Deployment) -> V1Deployment:
        """Scale a deployment to zero replicas and wait until all replicas have stopped.

        Args:
            deployment: The deployment to stop.

        Returns:
            V1Deployment: The updated deployment once all replicas reach zero.
        """
        deployment.autoscaling.min_replicas = 0
        deployment.autoscaling.max_replicas = 0

        deployment = self._client.jobs_service_update_deployment(
            project_id=deployment.project_id,
            id=deployment.id,
            body=deployment,
        )

        # wait for all the replicas to be 0
        while deployment.replicas != 0:
            sleep(self._wait_on_stop)
            deployment = self.get_deployment_by_name(deployment.name, deployment.project_id)

        return deployment

    def export_request_captures(
        self,
        deployment: V1Deployment,
        *,
        start: DateTimeLike,
        end: DateTimeLike,
        output_dir: PathLike,
        paths: Optional[Sequence[str]] = None,
        include_all_paths: bool = False,
        status_codes: Optional[Sequence[int]] = None,
        page_size: int = 500,
        max_pages: Optional[int] = None,
        strict: bool = False,
        request_timeout: Union[float, tuple] = 60,
        overwrite: bool = False,
        remote_path: Optional[str] = None,
    ) -> RequestCaptureExportResult:
        """Export captured request telemetry for a deployment to local artifacts.

        The export is always written to ``output_dir``. If ``remote_path`` is provided,
        the same artifacts are also uploaded remotely. This currently supports
        ``lightning_storage`` destinations only.

        Args:
            deployment: The deployment whose request captures to export.
            start: Start of the time range to export (datetime or ISO string).
            end: End of the time range to export (datetime or ISO string).
            output_dir: Local directory to write CSV, JSONL, and manifest files.
            paths: URL paths to filter; defaults to ``["/v1/chat/completions"]``.
            include_all_paths: When ``True``, export all paths regardless of ``paths``.
            status_codes: HTTP status codes to filter; defaults to all codes.
            page_size: Number of records to fetch per API page.
            max_pages: Maximum number of pages to fetch; ``None`` means no limit.
            strict: When ``True``, raise on any content download error.
            request_timeout: Timeout in seconds for individual content download requests.
            overwrite: When ``True``, overwrite existing output files.
            remote_path: Optional ``lightning_storage`` destination path for remote upload.

        Returns:
            RequestCaptureExportResult: Paths and counts for the exported artifacts.
        """
        return _export_deployment_request_captures(
            client=self._client,
            teamspace_id=deployment.project_id,
            deployment_id=deployment.id,
            deployment_name=deployment.name,
            start=start,
            end=end,
            output_dir=output_dir,
            paths=paths,
            include_all_paths=include_all_paths,
            status_codes=status_codes,
            page_size=page_size,
            max_pages=max_pages,
            strict=strict,
            request_timeout=request_timeout,
            overwrite=overwrite,
            remote_path=remote_path,
        )


def _export_deployment_request_captures(
    *,
    client: Any,
    teamspace_id: str,
    deployment_id: str,
    deployment_name: Optional[str],
    start: DateTimeLike,
    end: DateTimeLike,
    output_dir: PathLike,
    paths: Optional[Sequence[str]] = None,
    include_all_paths: bool = False,
    status_codes: Optional[Sequence[int]] = None,
    page_size: int = 500,
    max_pages: Optional[int] = None,
    strict: bool = False,
    request_timeout: Union[float, tuple] = 60,
    overwrite: bool = False,
    remote_path: Optional[str] = None,
) -> RequestCaptureExportResult:
    if start is None or end is None:
        raise ValueError("start and end are required for request capture export")
    if include_all_paths and paths is not None:
        raise ValueError("include_all_paths and paths are mutually exclusive")
    if paths is not None and not paths:
        raise ValueError("paths must not be empty")
    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be greater than 0")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "requests.csv"
    jsonl_path = output_path / "requests.jsonl"
    manifest_path = output_path / "manifest.json"
    _validate_artifact_paths([csv_path, jsonl_path, manifest_path], overwrite=overwrite)

    if include_all_paths:
        path_filter = None
    elif paths is None:
        path_filter = [DEFAULT_REQUEST_CAPTURE_PATH]
    else:
        path_filter = list(paths)
    status_filter = None if status_codes is None else list(status_codes)
    planned_upload_target = None
    if remote_path is not None:
        _validate_remote_upload_path_target(
            client=client,
            teamspace_id=teamspace_id,
            remote_path=remote_path,
        )
        folder_name, relative_parts = _parse_lightning_storage_path(remote_path)
        planned_upload_target = _LightningStorageUploadTarget(
            data_connection_id="",
            cloud_account=None,
            folder_name=folder_name,
            relative_parts=relative_parts,
        )

    counts = {
        "row_count": 0,
        "captured_count": 0,
        "uncaptured_count": 0,
        "missing_content_count": 0,
        "content_error_count": 0,
    }
    last_request_id = None
    seen_page_boundaries = set()
    pages_fetched = 0

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file, jsonl_path.open(
            "w", encoding="utf-8"
        ) as jsonl_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=_CSV_FIELDNAMES)
            csv_writer.writeheader()

            while max_pages is None or pages_fetched < max_pages:
                query_kwargs = {
                    "project_id": teamspace_id,
                    "id": deployment_id,
                    "start": start,
                    "end": end,
                    "limit": page_size,
                }
                if path_filter is not None:
                    query_kwargs["path"] = path_filter
                if status_filter is not None:
                    query_kwargs["status_code"] = status_filter
                if last_request_id is not None:
                    query_kwargs["last_request_id"] = last_request_id

                response = client.jobs_service_list_deployment_routing_telemetry(**query_kwargs)
                telemetry_items = list(getattr(response, "routing_telemetry", None) or [])
                pages_fetched += 1

                for telemetry in telemetry_items:
                    row = _build_export_row(
                        client=client,
                        teamspace_id=teamspace_id,
                        deployment_id=deployment_id,
                        telemetry=telemetry,
                        strict=strict,
                        request_timeout=request_timeout,
                    )
                    _update_counts(counts, row)
                    _write_row(csv_writer, jsonl_file, row)

                if len(telemetry_items) < page_size:
                    break

                next_last_request_id = getattr(telemetry_items[-1], "id", None)
                if not next_last_request_id or next_last_request_id in seen_page_boundaries:
                    break
                seen_page_boundaries.add(next_last_request_id)
                last_request_id = next_last_request_id
        manifest = _build_manifest(
            teamspace_id=teamspace_id,
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            start=start,
            end=end,
            paths=path_filter,
            include_all_paths=include_all_paths,
            status_codes=status_filter,
            page_size=page_size,
            pages_fetched=pages_fetched,
            counts=counts,
            csv_path=csv_path,
            jsonl_path=jsonl_path,
        )
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        if strict:
            _remove_artifacts([csv_path, jsonl_path, manifest_path])
        raise

    uploaded_artifacts = None
    if planned_upload_target is not None:
        uploaded_artifacts = {
            "csv": planned_upload_target.absolute_artifact_path(csv_path.name),
            "jsonl": planned_upload_target.absolute_artifact_path(jsonl_path.name),
            "manifest": planned_upload_target.absolute_artifact_path(manifest_path.name),
        }
        upload_target = _resolve_lightning_storage_upload_target(
            client=client,
            teamspace_id=teamspace_id,
            remote_path=remote_path,
        )
        partial_uploaded_artifacts = {}
        for artifact_name, local_artifact_path in (("csv", csv_path), ("jsonl", jsonl_path)):
            _upload_request_export_artifact(
                client=client,
                teamspace_id=teamspace_id,
                upload_target=upload_target,
                local_path=local_artifact_path,
            )
            partial_uploaded_artifacts[artifact_name] = uploaded_artifacts[artifact_name]
            manifest["uploaded_artifacts"] = dict(partial_uploaded_artifacts)
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with TemporaryDirectory(dir=output_path) as tmp_dir:
            manifest_upload_path = Path(tmp_dir) / manifest_path.name
            manifest_payload = dict(manifest)
            manifest_payload["uploaded_artifacts"] = uploaded_artifacts
            manifest_upload_path.write_text(
                json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            _upload_request_export_artifact(
                client=client,
                teamspace_id=teamspace_id,
                upload_target=upload_target,
                local_path=manifest_upload_path,
            )
        manifest["uploaded_artifacts"] = uploaded_artifacts
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return RequestCaptureExportResult(
        output_dir=output_path,
        manifest_path=manifest_path,
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        row_count=manifest["row_count"],
        captured_count=manifest["captured_count"],
        uncaptured_count=manifest["uncaptured_count"],
        missing_content_count=manifest["missing_content_count"],
        content_error_count=manifest["content_error_count"],
        uploaded_artifacts=uploaded_artifacts,
    )


def _build_export_row(
    *,
    client: Any,
    teamspace_id: str,
    deployment_id: str,
    telemetry: Any,
    strict: bool,
    request_timeout: Union[float, tuple],
) -> Dict[str, Any]:
    """Build a flat export row dict from a routing telemetry entry, downloading captured content if available.

    Returns:
        Dict[str, Any]: A flat dictionary of request metadata and optionally decoded request/response bodies.
    """
    row = {
        "request_id": getattr(telemetry, "id", None),
        "received_at": _serialize_datetime(getattr(telemetry, "received_at", None)),
        "status_code": getattr(telemetry, "status_code", None),
        "method": getattr(telemetry, "method", None),
        "path": getattr(telemetry, "path", None),
        "latency_ms": _duration_to_milliseconds(getattr(telemetry, "duration", None)),
        "resource_id": getattr(telemetry, "resource_id", None),
        "captured": bool(getattr(telemetry, "captured", False)),
        "request_body_size": getattr(telemetry, "request_body_size", None),
        "response_body_size": getattr(telemetry, "response_body_size", None),
        "request_body": None,
        "response_body": None,
        "raw_content": None,
        "content_missing": False,
        "content_error": None,
    }

    if not row["captured"]:
        return row

    try:
        payload = _download_request_content(
            client=client,
            teamspace_id=teamspace_id,
            deployment_id=deployment_id,
            request_id=row["request_id"],
            request_timeout=request_timeout,
        )
    except MissingRequestContentError as ex:
        if strict:
            raise
        row["content_missing"] = True
        row["content_error"] = str(ex)
        return row
    except requests.RequestException as ex:
        if strict:
            raise
        row["content_error"] = str(ex)
        return row
    except Exception as ex:
        if strict:
            raise
        row["content_error"] = f"failed to download captured content: {ex}"
        return row

    try:
        content = json.loads(payload)
    except json.JSONDecodeError as ex:
        row["raw_content"] = payload
        row["content_error"] = f"failed to parse captured content: {ex}"
        return row

    row["request_body"] = content.get("request_body")
    row["response_body"] = content.get("response_body")
    return row


def _download_request_content(
    *,
    client: Any,
    teamspace_id: str,
    deployment_id: str,
    request_id: Optional[str],
    request_timeout: Union[float, tuple],
) -> str:
    """Download and decode the body content for a captured request.

    Args:
        client: The API client used to fetch the content URL.
        teamspace_id: ID of the teamspace that owns the deployment.
        deployment_id: ID of the deployment.
        request_id: ID of the captured request whose content to retrieve.
        request_timeout: Timeout for the HTTP download request.

    Returns:
        str: The decoded (UTF-8) body content of the captured request.

    Raises:
        MissingRequestContentError: If request_id is absent, the content URL is
            missing, or the content cannot be found (404).
    """
    if not request_id:
        raise MissingRequestContentError("missing request id for captured request content")

    response = client.jobs_service_get_deployment_routing_telemetry_content(
        project_id=teamspace_id,
        id=deployment_id,
        request_id=request_id,
    )
    url = getattr(response, "url", None)
    if not url:
        raise MissingRequestContentError(f"missing content URL for request {request_id}")

    download = requests.get(url, timeout=request_timeout)
    if download.status_code == 404:
        raise MissingRequestContentError(f"captured content not found for request {request_id}")
    download.raise_for_status()
    return _decode_content(download.content)


def _decode_content(content: bytes) -> str:
    if len(content) >= 2 and content[0] == 0x1F and content[1] == 0x8B:
        content = gzip.decompress(content)
    return content.decode("utf-8")


def _validate_artifact_paths(paths: Sequence[Path], *, overwrite: bool) -> None:
    if overwrite:
        return
    existing_paths = [str(path) for path in paths if path.exists()]
    if existing_paths:
        raise FileExistsError(f"export artifact already exists: {', '.join(existing_paths)}")


def _remove_artifacts(paths: Sequence[Path]) -> None:
    for path in paths:
        with suppress(OSError):
            path.unlink(missing_ok=True)


def _resolve_lightning_storage_upload_target(
    *,
    client: Any,
    teamspace_id: str,
    remote_path: str,
) -> _LightningStorageUploadTarget:
    _validate_remote_upload_path_target(
        client=client,
        teamspace_id=teamspace_id,
        remote_path=remote_path,
    )
    resolved_target = lightning_storage_upload_api.resolve_lightning_storage_upload_target(
        client=client,
        teamspace_id=teamspace_id,
        remote_path=remote_path,
    )
    return _LightningStorageUploadTarget(
        data_connection_id=resolved_target.data_connection_id,
        cloud_account=resolved_target.cloud_account,
        folder_name=resolved_target.folder_name,
        relative_parts=resolved_target.relative_parts,
    )


def _validate_remote_upload_path_target(*, client: Any, teamspace_id: str, remote_path: str) -> None:
    normalized = str(remote_path or "").strip()
    if not normalized.startswith("lit://"):
        return

    parsed = parse_lit_url(normalized)
    parsed_teamspace = str(parsed.get("teamspace", "") or "").strip()
    if not parsed_teamspace:
        raise ValueError("remote_path lit URL must include a non-empty teamspace")

    parsed_owner = str(parsed.get("owner", "") or "").strip()
    if not parsed_owner:
        raise ValueError("remote_path lit URL must include a non-empty owner")

    project = client.projects_service_get_project(teamspace_id)
    expected_teamspace = str(getattr(project, "name", "") or "").strip()
    if expected_teamspace and parsed_teamspace != expected_teamspace:
        raise ValueError(
            "remote_path lit URL must target the current deployment teamspace "
            f"(expected teamspace '{expected_teamspace}', got '{parsed_teamspace}')"
        )

    expected_owner = _resolve_project_owner_name(client=client, project=project)
    if expected_owner and parsed_owner != expected_owner:
        raise ValueError(
            "remote_path lit URL must target the current deployment teamspace "
            f"(expected owner '{expected_owner}', got '{parsed_owner}')"
        )


def _extract_lit_remote_destination(remote_path: str) -> str:
    return lightning_storage_upload_api._extract_lit_remote_destination(remote_path)


def _resolve_project_owner_name(*, client: Any, project: Any) -> str:
    owner_id = str(getattr(project, "owner_id", "") or "").strip()
    owner_type = str(getattr(project, "owner_type", "") or "").strip().lower()

    if not owner_id or not owner_type:
        return ""

    if owner_type == "organization":
        organization = client.organizations_service_get_organization(id=owner_id)
        return str(getattr(organization, "name", "") or "").strip()

    if owner_type == "user":
        response = client.user_service_search_users(query=owner_id)
        users = list(getattr(response, "users", None) or [])
        for user in users:
            if getattr(user, "id", None) == owner_id:
                return str(getattr(user, "username", "") or "").strip()

    return ""


def _parse_lightning_storage_path(remote_path: str) -> Tuple[str, Tuple[str, ...]]:
    return lightning_storage_upload_api._parse_lightning_storage_path(remote_path)


def _get_or_create_lightning_storage_folder(
    *,
    client: Any,
    teamspace_id: str,
    folder_name: str,
) -> Any:
    return lightning_storage_upload_api._get_or_create_lightning_storage_folder(
        client=client,
        teamspace_id=teamspace_id,
        folder_name=folder_name,
    )


def _resolve_lightning_storage_upload_cloud_account(*, client: Any, teamspace_id: str) -> str:
    return lightning_storage_upload_api._resolve_lightning_storage_upload_cloud_account(
        client=client,
        teamspace_id=teamspace_id,
    )


def _find_lightning_storage_folder(*, client: Any, teamspace_id: str, folder_name: str) -> Optional[Any]:
    return lightning_storage_upload_api._find_lightning_storage_folder(
        client=client,
        teamspace_id=teamspace_id,
        folder_name=folder_name,
    )


def _is_lightning_storage_folder_ready(connection: Any) -> bool:
    return lightning_storage_upload_api._is_lightning_storage_folder_ready(connection)


def _wait_for_lightning_storage_folder_ready(
    *,
    client: Any,
    teamspace_id: str,
    folder_name: str,
    initial_connection: Optional[Any] = None,
    timeout_seconds: int = lightning_storage_upload_api.LIGHTNING_STORAGE_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: int = lightning_storage_upload_api.LIGHTNING_STORAGE_POLL_INTERVAL_SECONDS,
) -> Any:
    return lightning_storage_upload_api._wait_for_lightning_storage_folder_ready(
        client=client,
        teamspace_id=teamspace_id,
        folder_name=folder_name,
        initial_connection=initial_connection,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


def _upload_request_export_artifact(
    *,
    client: Any,
    teamspace_id: str,
    upload_target: _LightningStorageUploadTarget,
    local_path: Path,
) -> None:
    try:
        lightning_storage_upload_api.upload_file_to_resolved_lightning_storage_target(
            client=client,
            teamspace_id=teamspace_id,
            upload_target=lightning_storage_upload_api.LightningStorageUploadTarget(
                data_connection_id=upload_target.data_connection_id,
                cloud_account=upload_target.cloud_account,
                folder_name=upload_target.folder_name,
                relative_parts=upload_target.relative_parts,
            ),
            local_path=local_path,
            destination_parts=(local_path.name,),
            progress_bar=False,
            uploader_cls=_FileUploader,
        )
    except Exception as ex:
        destination = upload_target.absolute_artifact_path(local_path.name)
        raise RuntimeError(f"failed to upload request export artifact '{local_path.name}' to {destination}") from ex


def _update_counts(counts: Dict[str, int], row: Dict[str, Any]) -> None:
    counts["row_count"] += 1
    if row["captured"]:
        counts["captured_count"] += 1
    else:
        counts["uncaptured_count"] += 1
    if row["content_missing"]:
        counts["missing_content_count"] += 1
    if row["content_error"] and not row["content_missing"]:
        counts["content_error_count"] += 1


def _write_row(csv_writer: csv.DictWriter, jsonl_file: TextIO, row: Dict[str, Any]) -> None:
    csv_writer.writerow({field: _csv_value(row.get(field)) for field in _CSV_FIELDNAMES})
    jsonl_file.write(json.dumps(row, default=_json_default, sort_keys=True) + "\n")


def _build_manifest(
    *,
    teamspace_id: str,
    deployment_id: str,
    deployment_name: Optional[str],
    start: DateTimeLike,
    end: DateTimeLike,
    paths: Optional[Sequence[str]],
    include_all_paths: bool,
    status_codes: Optional[Sequence[int]],
    page_size: int,
    pages_fetched: int,
    counts: Dict[str, int],
    csv_path: Path,
    jsonl_path: Path,
) -> Dict[str, Any]:
    return {
        "teamspace_id": teamspace_id,
        "deployment_id": deployment_id,
        "deployment_name": deployment_name,
        "start": _serialize_datetime(start),
        "end": _serialize_datetime(end),
        "paths": list(paths) if paths is not None else None,
        "include_all_paths": include_all_paths,
        "status_codes": list(status_codes) if status_codes is not None else None,
        "page_size": page_size,
        "pages_fetched": pages_fetched,
        "row_count": counts["row_count"],
        "captured_count": counts["captured_count"],
        "uncaptured_count": counts["uncaptured_count"],
        "missing_content_count": counts["missing_content_count"],
        "content_error_count": counts["content_error_count"],
        "artifacts": {
            "csv": str(csv_path),
            "jsonl": str(jsonl_path),
        },
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=_json_default, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _serialize_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _duration_to_milliseconds(value: Any) -> Any:
    if value is None:
        return None
    total_seconds = getattr(value, "total_seconds", None)
    if callable(total_seconds):
        return int(total_seconds() * 1000)
    return value


def _json_default(value: Any) -> str:
    return _serialize_datetime(value) or str(value)


def restore_release_strategy(strategy: V1DeploymentStrategy) -> Optional[ReleaseStrategy]:
    if not strategy:
        return None

    if strategy.rolling_update:
        return RollingUpdateReleaseStrategy(
            max_surge=strategy.rolling_update.max_surge,
            max_unavailable=strategy.rolling_update.max_unavailable,
        )
    raise ValueError("Only rolling update is supported for deployment. Stay tuned for more.")


def restore_health_check(readiness_probe: V1JobHealthCheckConfig) -> Optional[Union[HttpHealthCheck, ExecHealthCheck]]:
    if not readiness_probe:
        return None

    if readiness_probe.exec:
        return ExecHealthCheck(
            command=readiness_probe.exec.comand,
            failure_threshold=readiness_probe.failure_threshold,
            initial_delay_seconds=readiness_probe.initial_delay_seconds,
            interval_seconds=readiness_probe.interval_seconds,
            timeout_seconds=readiness_probe.timeout_seconds,
        )

    if readiness_probe.http_get:
        return HttpHealthCheck(
            path=readiness_probe.http_get.path,
            port=readiness_probe.http_get.port,
            failure_threshold=readiness_probe.failure_threshold,
            initial_delay_seconds=readiness_probe.initial_delay_seconds,
            interval_seconds=readiness_probe.interval_seconds,
            timeout_seconds=readiness_probe.timeout_seconds,
        )
    return None


def restore_auth(auth: Optional[V1EndpointAuth] = None) -> Optional[Auth]:
    if not auth:
        return None

    if auth.user_api_key:
        return ApiKeyAuth()

    if auth.username and auth.password:
        return BasicAuth(username=auth.username, password=auth.password)

    if auth.token:
        return TokenAuth(token=auth.token)

    return None


def restore_autoscale(autoscaling: V1AutoscalingSpec) -> AutoScaleConfig:
    return [
        AutoScaleConfig(
            min_replicas=autoscaling.min_replicas,
            max_replicas=autoscaling.max_replicas,
            target_metrics=autoscaling.target_metric,
            idle_threshold_seconds=autoscaling.idle_threshold_seconds,
            scale_down_cooldown_seconds=autoscaling.scale_down_cooldown_seconds,
            scale_up_cooldown_seconds=autoscaling.scale_up_cooldown_seconds,
        )
    ]


def restore_env(env: List[V1EnvVar]) -> List[Union[Secret, Env]]:
    return [Secret(name=e.from_secret) if e.from_secret else Env(name=e.name, value=e.value) for e in env]


def to_env(env: Union[List[Union[Secret, Env]], Dict[str, str], None] = None) -> Optional[List[V1EnvVar]]:
    if not env:
        return None

    env_list = []

    if isinstance(env, dict):
        for k, v in env.items():
            env_list.append(Env(name=k, value=v))
    else:
        env_list = env

    return [
        V1EnvVar(name=env.name, value=env.value) if isinstance(env, Env) else V1EnvVar(from_secret=env.name)
        for env in env_list
    ]


def to_autoscaling(
    autoscale_config: Optional[AutoScaleConfig] = None, replicas: Optional[int] = None
) -> V1AutoscalingSpec:
    if not autoscale_config:
        raise ValueError("An autoscaling config should be provided.")

    min_replicas = autoscale_config.min_replicas
    max_replicas = autoscale_config.max_replicas
    metric = autoscale_config.metric
    threshold = autoscale_config.threshold
    target_metrics = autoscale_config.target_metrics

    if isinstance(replicas, int) and replicas < 0:
        raise ValueError("The number of replicas should be positive.")

    if isinstance(min_replicas, int) and min_replicas < 0:
        raise ValueError("The minimum number of replicas should be positive.")

    if isinstance(max_replicas, int) and max_replicas < 0:
        raise ValueError("The maximum number of replicas should be positive.")

    if min_replicas is None:
        if isinstance(replicas, int):
            print(f"The `min_replicas` wasn't provided. Defaulting to replicas: {replicas}.")
        else:
            print("The `min_replicas` wasn't provided. Defaulting to 0.")
            min_replicas = 0

    if max_replicas is None:
        if isinstance(replicas, int):
            print(f"The `max_replicas` wasn't provided. Defaulting to replicas: {replicas}.")
        else:
            print("The `max_replicas` wasn't provided. Defaulting to 1.")
            max_replicas = 1

    if min_replicas < 0:
        raise ValueError("The minimum number of replicas should be positive.")

    if min_replicas > max_replicas:
        raise ValueError("The minimum number of replicas should be smaller or equal to the maximum number of replicas.")

    if (metric is not None or threshold is not None) and target_metrics is not None:
        raise ValueError("Either metric and threshold, or target_metrics (for multiple) can be provided.")

    if target_metrics is None and (metric is None or (isinstance(metric, str) and metric not in _METRICS)):
        raise ValueError(f"The autoscaling metric is required. Currently supported metrics are {_METRICS}")

    if target_metrics is None and threshold is None:
        raise ValueError("The autoscaling threshold should be defined between 0 and 100.")

    if target_metrics is None and (threshold < 0 or threshold > 100):
        raise ValueError("The autoscaling threshold should be defined between 0 and 100.")

    if target_metrics is not None and len(target_metrics) == 0 and metric is None:
        raise ValueError("The target_metrics must be provided.")

    if target_metrics is not None:
        for target_metric in target_metrics:
            if target_metric.name is None or target_metric.name not in _METRICS:
                raise ValueError(f"The autoscaling metric is required. Currently supported metrics are {_METRICS}")
            if target_metric.target is None or target_metric.target < 0 or target_metric.target > 100:
                raise ValueError("The autoscaling threshold should be defined between 0 and 100.")

            # convert to string after validation
            target_metric.target = str(target_metric.target)

    metrics = (
        [V1AutoscalingTargetMetric(name=t.name, target=t.target) for t in target_metrics]
        if target_metrics is not None
        else [V1AutoscalingTargetMetric(name=metric, target=str(threshold))]
    )

    return V1AutoscalingSpec(
        enabled=True,
        min_replicas=min_replicas,
        max_replicas=max_replicas,
        target_metric=metrics,
        idle_threshold_seconds=autoscale_config.idle_threshold_seconds,
        scale_down_cooldown_seconds=autoscale_config.scale_down_cooldown_seconds,
        scale_up_cooldown_seconds=autoscale_config.scale_up_cooldown_seconds,
    )


def to_endpoint_auth(auth: Optional[Auth] = None) -> Optional[V1EndpointAuth]:
    if isinstance(auth, BasicAuth):
        if auth.username == "":
            raise ValueError("The username should be defined.")

        if auth.password == "":
            raise ValueError("The password should be defined.")

        return V1EndpointAuth(enabled=True, username=auth.username, password=auth.password)

    if isinstance(auth, TokenAuth):
        if auth.token == "":
            raise ValueError("The token should be defined.")

        return V1EndpointAuth(enabled=True, token=auth.token)

    if isinstance(auth, ApiKeyAuth):
        return V1EndpointAuth(enabled=True, user_api_key=True)

    return None


def to_endpoint(
    ports: Optional[List[float]] = None, auth: Optional[Auth] = None, custom_domain: Optional[str] = None
) -> V1Endpoint:
    if not ports:
        raise ValueError("At least one port is required to reach your deployment.")

    return V1Endpoint(
        auth=to_endpoint_auth(auth),
        custom_domain=custom_domain,
        ports=[str(port) for port in ports],
    )


def to_health_check(
    health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
    use_default: bool = True,
) -> Optional[V1JobHealthCheckConfig]:
    if health_check is None and not use_default:
        return None

    # Use Default health check if none is provided
    if not health_check:
        return V1JobHealthCheckConfig(
            failure_threshold=3600,
            initial_delay_seconds=0,
            interval_seconds=1,
            timeout_seconds=60,
        )

    health_check_config = V1JobHealthCheckConfig(
        failure_threshold=health_check.failure_threshold,
        initial_delay_seconds=health_check.initial_delay_seconds,
        interval_seconds=health_check.interval_seconds,
        timeout_seconds=health_check.timeout_seconds,
    )

    if isinstance(health_check, HttpHealthCheck):
        health_check_config.http_get = V1HealthCheckHttpGet(
            path=health_check.path,
            port=health_check.port,
        )
    else:
        health_check_config._exec = V1HealthCheckExec(command=health_check.command)
    return health_check_config


def to_spec(
    cloud_account: Optional[str],
    machine: Optional[Machine],
    image: Optional[str],
    entrypoint: Optional[str],
    command: Optional[str],
    spot: Optional[bool] = False,
    env: Union[List[Union[Secret, Env]], Dict[str, str], None] = None,
    health_check: Optional[Union[HttpHealthCheck, ExecHealthCheck]] = None,
    quantity: Optional[int] = None,
    include_credentials: Optional[bool] = None,
    cloudspace_id: Optional[str] = None,
    max_runtime: Optional[int] = None,
    machine_image_version: Optional[str] = None,
    path_mappings: Optional[Dict[str, str]] = None,
    byom: bool = False,
) -> V1JobSpec:
    if cloud_account is None:
        raise ValueError("The cloud account should be defined.")

    if machine is None:
        raise ValueError("The machine should be defined.")

    # BYOM deploys carry no client-side image; the server compiles one from the byom_spec.
    if image is None and cloudspace_id is None and not byom:
        raise ValueError("The image should be defined.")

    if entrypoint is not None and cloudspace_id is not None:
        raise ValueError("The entrypoint shouldn't be defined when a Studio is provided.")

    if command is None and cloudspace_id is not None:
        raise ValueError("The command should be defined.")

    # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
    optional_spec_kwargs = {}
    if max_runtime:
        optional_spec_kwargs["requested_run_duration_seconds"] = str(max_runtime)

    path_mapping_list = resolve_path_mappings(path_mappings or {}, None, None)

    return V1JobSpec(
        cluster_id=cloud_account,
        command=command,
        entrypoint=entrypoint,
        env=to_env(env),
        image=image,
        spot=spot,
        instance_name=_machine_to_compute_name(machine),
        readiness_probe=to_health_check(health_check),
        quantity=quantity,
        include_credentials=include_credentials,
        cloudspace_id=cloudspace_id,
        machine_image_version=machine_image_version,
        path_mappings=path_mapping_list,
        **optional_spec_kwargs,
    )


def to_strategy(strategy: Optional[ReleaseStrategy]) -> None:
    if isinstance(strategy, RollingUpdateReleaseStrategy):
        return V1DeploymentStrategy(
            rolling_update=V1RollingUpdateStrategy(
                max_surge=strategy.max_surge,
                max_unavailable=strategy.max_unavailable,
            ),
            type="rolling_update",
        )
    return None


def to_byom_spec(
    model: Optional[str],
    *,
    hf_token_secret: Optional[str] = None,
    base_image_variant: Optional[str] = None,
    tensor_parallel_size: Optional[int] = None,
    max_model_len: Optional[int] = None,
    gpu_memory_utilization: Optional[float] = None,
    quantization: Optional[str] = None,
    dtype: Optional[str] = None,
    extra_vllm_args: Optional[Sequence[str]] = None,
) -> Optional[V1BYOMSpec]:
    if not model:
        return None
    return V1BYOMSpec(
        served_model_name=model,
        weight_source=V1WeightSource.HUGGINGFACE,
        hf_token_secret_name=hf_token_secret,
        base_image_variant=base_image_variant,
        tensor_parallel_size=tensor_parallel_size,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        quantization=quantization,
        dtype=dtype,
        extra_vllm_args=list(extra_vllm_args) if extra_vllm_args else None,
    )


def apply_change(spec: Any, key: str, value: Any) -> bool:
    if value is None:
        return False

    if getattr(spec, key) != value:
        setattr(spec, key, value)
        return True

    return False


def compose_commands(commands: List[str]) -> str:
    composite_command = []

    for command in commands:
        command = command.strip()

        # Check if the command already has '&'
        if command.endswith("&"):
            # It's a background command, add it as a subshell without further adjustment
            composite_command.append(f"( {command} )")
        else:
            # Sequential execution, add as-is and use `&&` to connect if followed by another command
            composite_command.append(command)

    # Joining commands, using `&&` between sequential parts and respecting subshell backgrounds
    return " && ".join(composite_command)
