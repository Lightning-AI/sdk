import json
import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import urlopen

from lightning_sdk.api.utils import _get_cloud_url as _cloud_url
from lightning_sdk.api.utils import (
    _machine_to_compute_name,
    remove_datetime_prefix,
    resolve_path_mappings,
)
from lightning_sdk.constants import __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import (
    JobsServiceCreateJobBody,
    JobsServiceUpdateJobBody,
    V1CloudSpace,
    V1ClusterAccelerator,
    V1DownloadJobLogsResponse,
    V1EnvVar,
    V1Job,
    V1JobSpec,
    V1Volume,
)
from lightning_sdk.lightning_cloud.rest_client import LightningClient
from lightning_sdk.machine import Machine

if TYPE_CHECKING:
    from lightning_sdk.status import Status

# While following, recv() is given this timeout so we can periodically check whether the job has
# finished. It must stay below the server's log-socket heartbeat (10s) so recv() actually wakes up
# during quiet periods.
_FOLLOW_POLL_INTERVAL = 5.0


def _job_logs_ws_url(
    teamspace_id: str,
    job_id: str,
    *,
    follow: bool,
    tail: Optional[int],
    rank: Optional[int],
) -> str:
    """Build the ``wss://`` URL for following a job's logs over the controlplane websocket."""
    parsed = urlparse(f"/v1/projects/{teamspace_id}/jobs/{job_id}/logs")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"follow": str(follow).lower(), "direction": "forward"})
    if rank is not None:
        query["rank"] = str(rank)
    if tail is not None:
        query["tail"] = str(tail)
    path = urlunparse(parsed._replace(query=urlencode(query)))

    absolute = f"{_cloud_url().rstrip('/')}/{path.lstrip('/')}"
    if absolute.startswith("https://"):
        return "wss://" + absolute[len("https://") :]
    if absolute.startswith("http://"):
        return "ws://" + absolute[len("http://") :]
    return absolute


def _format_log_timestamp(value: object) -> Optional[str]:
    """Best-effort convert a ``LogEntry`` timestamp into an ISO-8601 string.

    The controlplane serialises the protobuf ``Timestamp`` as ``{"seconds": ..., "nanos": ...}``,
    but we also accept an already-formatted string in case that ever changes.
    """
    if isinstance(value, dict):
        seconds = value.get("seconds")
        if seconds is None:
            return None
        epoch = float(seconds) + float(value.get("nanos", 0)) / 1e9
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    if isinstance(value, str) and value:
        return value
    return None


def _decode_log_messages(message: str, *, timestamps: bool = False) -> Iterator[str]:
    """Decode a websocket log frame into individual log lines.

    Args:
        message: A raw websocket text frame (usually a JSON array of log entries).
        timestamps: When ``True``, prepend each line with its ISO-8601 timestamp if available.
    """
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        yield message
        return

    entries = payload if isinstance(payload, list) else [payload]
    for entry in entries:
        if isinstance(entry, dict):
            line = entry.get("message") or entry.get("Message") or json.dumps(entry)
            if timestamps:
                ts = _format_log_timestamp(entry.get("timestamp") or entry.get("Timestamp"))
                if ts:
                    line = f"{ts} {line}"
            yield line
        else:
            yield str(entry)


class JobApiV2:
    """Native (v2 jobs-service) API client for single-machine Jobs."""

    # these are stages the job can be in.
    v2_job_state_pending = "pending"
    v2_job_state_running = "running"
    v2_job_state_stopped = "stopped"
    v2_job_state_completed = "completed"
    v2_job_state_failed = "failed"
    v2_job_state_stopping = "stopping"

    # this is the user action to stop the job.
    v2_job_state_stop = "stop"

    def __init__(self) -> None:
        self._cloud_url = _cloud_url()
        self._client = LightningClient(max_tries=7)

    def submit_job(
        self,
        name: str,
        command: Optional[str],
        cloud_account: Optional[str],
        teamspace_id: str,
        studio_id: Optional[str],
        image: Optional[str],
        machine: Union[Machine, str],
        interruptible: bool,
        env: Optional[Dict[str, str]],
        image_credentials: Optional[str],
        cloud_account_auth: bool,
        entrypoint: str,
        path_mappings: Optional[Dict[str, str]],
        max_runtime: Optional[int] = None,
        reuse_snapshot: bool = True,
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
    ) -> V1Job:
        """Submit a v2 job and return the created job object.

        Args:
            name: The name to assign to the new job.
            command: The shell command the job will execute, or ``None`` when using a custom entrypoint.
            cloud_account: The cloud account identifier to use for compute, or ``None`` to use the default.
            teamspace_id: The ID of the teamspace that will own the job.
            studio_id: The ID of the Studio from which the job is launched, or ``None``.
            image: The container image to run, or ``None`` to use the Studio snapshot.
            machine: The machine type (as a ``Machine`` enum or a string slug) to run the job on.
            interruptible: Whether the job may run on interruptible (spot) instances.
            env: Optional mapping of environment variable names to values.
            image_credentials: Name of the secret holding image-pull credentials, or ``None``.
            cloud_account_auth: Whether to pass cloud-account credentials into the container.
            entrypoint: The entrypoint command used to launch the job process.
            path_mappings: Optional mapping of local paths to remote artifact destinations.
            max_runtime: Maximum allowed runtime in seconds, or ``None`` for no limit.
            reuse_snapshot: Whether to reuse the Studio's existing filesystem snapshot.
            scratch_disks: Optional mapping of scratch-disk mount paths to their sizes in GiB.
            placement_group_id: Optional placement group identifier for colocating the job.

        Returns:
            The newly created ``V1Job`` object.
        """
        if scratch_disks is not None:
            sanitized_scratch_disks = {}
            for k, v in scratch_disks.items():
                sanitized_k = k if k.startswith("/teamspace/scratch/") else f"/teamspace/scratch/{k}"
                sanitized_scratch_disks[sanitized_k] = v
        else:
            sanitized_scratch_disks = None

        body = self._create_job_body(
            name=name,
            command=command,
            cloud_account=cloud_account,
            studio_id=studio_id,
            image=image,
            machine=machine,
            interruptible=interruptible,
            env=env,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            max_runtime=max_runtime,
            reuse_snapshot=reuse_snapshot,
            scratch_disks=sanitized_scratch_disks,
            placement_group_id=placement_group_id,
        )

        job: V1Job = self._client.jobs_service_create_job(project_id=teamspace_id, body=body)
        return job

    @staticmethod
    def _create_job_body(
        name: str,
        command: Optional[str],
        cloud_account: Optional[str],
        studio_id: Optional[str],
        image: Optional[str],
        machine: Union[Machine, str],
        interruptible: bool,
        env: Optional[Dict[str, str]],
        image_credentials: Optional[str],
        cloud_account_auth: bool,
        entrypoint: str,
        path_mappings: Optional[Dict[str, str]],
        reuse_snapshot: bool,
        max_runtime: Optional[int] = None,
        machine_image_version: Optional[str] = None,
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
    ) -> JobsServiceCreateJobBody:
        """Build the request body for creating a v2 job.

        Args:
            name: The name to assign to the new job.
            command: The shell command the job will execute, or ``None`` when using a custom entrypoint.
            cloud_account: The cloud account identifier to use for compute, or ``None`` to use the default.
            studio_id: The ID of the Studio from which the job is launched, or ``None``.
            image: The container image to run, or ``None`` to use the Studio snapshot.
            machine: The machine type (as a ``Machine`` enum or a string slug) to run the job on.
            interruptible: Whether the job may run on interruptible (spot) instances.
            env: Optional mapping of environment variable names to values.
            image_credentials: Name of the secret holding image-pull credentials, or ``None``.
            cloud_account_auth: Whether to pass cloud-account credentials into the container.
            entrypoint: The entrypoint command used to launch the job process.
            path_mappings: Optional mapping of local paths to remote artifact destinations.
            reuse_snapshot: Whether to reuse the Studio's existing filesystem snapshot.
            max_runtime: Maximum allowed runtime in seconds, or ``None`` for no limit.
            machine_image_version: Pinned machine-image version string, or ``None`` for the default.
            scratch_disks: Optional mapping of scratch-disk mount paths to their sizes in GiB.
            placement_group_id: Optional placement group identifier for colocating the job.

        Returns:
            A fully populated ``JobsServiceCreateJobBody`` ready to be sent to the jobs service.
        """
        env_vars = []
        if env is not None:
            for k, v in env.items():
                env_vars.append(V1EnvVar(name=k, value=v))

        instance_name = _machine_to_compute_name(machine)

        run_id = __GLOBAL_LIGHTNING_UNIQUE_IDS_STORE__[studio_id] if (studio_id is not None and reuse_snapshot) else ""

        path_mappings_list = resolve_path_mappings(mappings=path_mappings or {})

        # need to go via kwargs for typing compatibility since autogenerated apis accept None but aren't typed with None
        optional_spec_kwargs = {}
        if max_runtime:
            optional_spec_kwargs["requested_run_duration_seconds"] = str(max_runtime)

        # don't do default dicts, as they'll be mutable. Create a fresh one here
        scratch_disks = scratch_disks or {}

        spec = V1JobSpec(
            cloudspace_id=studio_id or "",
            cluster_id=cloud_account or "",
            command=command or "",
            entrypoint=entrypoint,
            env=env_vars,
            image=image or "",
            instance_name=instance_name,
            run_id=run_id,
            spot=interruptible,
            image_cluster_credentials=cloud_account_auth,
            image_secret_ref=image_credentials or "",
            path_mappings=path_mappings_list,
            machine_image_version=machine_image_version,
            placement_group_id=placement_group_id,
            volumes=[V1Volume(path=k, size_gb=v, ephemeral=True) for k, v in scratch_disks.items()],
            **optional_spec_kwargs,
        )
        return JobsServiceCreateJobBody(name=name, spec=spec)

    def get_job_by_name(self, name: str, teamspace_id: str) -> V1Job:
        """Fetch a v2 job by its unique name within a teamspace.

        Args:
            name: The name of the job to look up.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``V1Job`` object.
        """
        job: V1Job = self._client.jobs_service_find_job(project_id=teamspace_id, name=name)
        return job

    def get_job(self, job_id: str, teamspace_id: str) -> V1Job:
        """Fetch a v2 job by its unique ID.

        Args:
            job_id: The unique identifier of the job to retrieve.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The matching ``V1Job`` object.
        """
        job: V1Job = self._client.jobs_service_get_job(project_id=teamspace_id, id=job_id)
        return job

    def stop_job(self, job_id: str, teamspace_id: str) -> None:
        """Request to stop a running v2 job and wait until it reaches a terminal state.

        Args:
            job_id: The unique identifier of the job to stop.
            teamspace_id: The ID of the teamspace that owns the job.
        """
        from lightning_sdk.status import Status

        current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)

        current_state = self._job_state_to_external(current_job.state)

        if current_state in (
            Status.Stopped,
            Status.Completed,
            Status.Failed,
        ):
            return

        if current_state != Status.Stopping:
            update_body = JobsServiceUpdateJobBody(state=self.v2_job_state_stop)
            self._client.jobs_service_update_job(body=update_body, project_id=teamspace_id, id=job_id)

        while True:
            current_job = self.get_job(job_id=job_id, teamspace_id=teamspace_id)
            if self._job_state_to_external(current_job.state) in (
                Status.Stopped,
                Status.Completed,
                Status.Stopped,
                Status.Failed,
            ):
                break
            time.sleep(1)

    def delete_job(self, job_id: str, teamspace_id: str, cloudspace_id: Optional[str]) -> None:
        """Permanently delete a v2 job.

        Args:
            job_id: The unique identifier of the job to delete.
            teamspace_id: The ID of the teamspace that owns the job.
            cloudspace_id: The ID of the Studio (cloudspace) associated with the job, or ``None``.
        """
        self._client.jobs_service_delete_job(project_id=teamspace_id, id=job_id, cloudspace_id=cloudspace_id or "")

    def get_logs_finished(self, job_id: str, teamspace_id: str) -> str:
        """Download and return the completed log output for a v2 job.

        Args:
            job_id: The unique identifier of the job whose logs are fetched.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            The decoded log text with datetime prefixes stripped.
        """
        resp: V1DownloadJobLogsResponse = self._client.jobs_service_download_job_logs(
            project_id=teamspace_id, id=job_id
        )

        data = urlopen(resp.url).read().decode("utf-8")
        return remove_datetime_prefix(str(data))

    def stream_logs(
        self,
        job_id: str,
        teamspace_id: str,
        *,
        follow: bool = True,
        tail: Optional[int] = None,
        rank: Optional[int] = None,
        idle_timeout: Optional[float] = None,
        reconnect: bool = True,
        timestamps: bool = False,
    ) -> Iterator[str]:
        """Yield job log lines live over the controlplane websocket.

        Reconnects automatically on transient drops while ``follow`` is set, so this can
        stay open for the full lifetime of a long-running job.

        Args:
            job_id: The unique identifier of the job whose logs are streamed.
            teamspace_id: The ID of the teamspace that owns the job.
            follow: Keep the stream open and yield new lines as they are produced.
            tail: Number of recent lines to emit before following.
            rank: Distributed job rank to stream from.
            idle_timeout: If set, stop the stream after this many seconds without data.
            reconnect: Reconnect on transient socket drops while following.
            timestamps: When ``True``, prepend each line with its ISO-8601 timestamp.

        Yields:
            Individual decoded log lines.
        """
        try:
            import websocket
            from websocket import (
                WebSocketConnectionClosedException,
                WebSocketTimeoutException,
            )
        except ImportError as ex:
            raise RuntimeError(
                "Streaming logs requires the 'websocket-client' package (pip install websocket-client)."
            ) from ex

        auth_header = Auth().authenticate()
        url = _job_logs_ws_url(teamspace_id, job_id, follow=follow, tail=tail, rank=rank)

        # For follow we poll recv() with a timeout so we can periodically check whether the job has
        # finished: the server keeps the socket open (heartbeats only) after a job ends rather than
        # closing it, so a plain blocking recv() would hang forever once the job is done.
        recv_timeout = idle_timeout if idle_timeout is not None else (_FOLLOW_POLL_INTERVAL if follow else None)

        while True:
            ws = None
            try:
                kwargs: Dict = {"header": [f"Authorization: {auth_header}"]}
                if recv_timeout is not None:
                    kwargs["timeout"] = recv_timeout
                ws = websocket.create_connection(url, **kwargs)
                while True:
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        if follow:
                            # quiet socket (heartbeats only): stop if the job is done, else keep waiting
                            if self._is_job_finished(job_id, teamspace_id):
                                return
                            continue
                        return  # idle timeout on a snapshot: treat the stream as finished
                    except WebSocketConnectionClosedException:
                        break  # fall through to reconnect logic
                    if message == "":
                        break
                    yield from _decode_log_messages(message, timestamps=timestamps)
            finally:
                if ws is not None:
                    with suppress(Exception):
                        ws.close()

            if not (follow and reconnect):
                return
            if self._is_job_finished(job_id, teamspace_id):
                return  # socket dropped and the job is done — nothing more to stream
            time.sleep(1)  # brief backoff before reconnecting, matches the CLI

    def get_studio_name(self, job: V1Job) -> Optional[str]:
        """Return the name of the Studio linked to this job, or ``None`` if none is attached.

        Args:
            job: The v2 job whose linked Studio name is resolved.

        Returns:
            The display name of the Studio, or ``None`` if the job has no associated Studio.
        """
        if job.spec.cloudspace_id:
            cs: V1CloudSpace = self._client.cloud_space_service_get_cloud_space(
                project_id=job.project_id, id=job.spec.cloudspace_id
            )
            return cs.name

        return None

    def get_image_name(self, job: V1Job) -> Optional[str]:
        """Return the container image used by this job, or ``None`` if not set.

        Args:
            job: The v2 job whose image name is retrieved.

        Returns:
            The container image string, or ``None`` if no image was specified.
        """
        return job.spec.image or None

    def get_command(self, job: V1Job) -> str:
        """Return the shell command that the job executes.

        Args:
            job: The v2 job whose command is retrieved.

        Returns:
            The shell command string stored in the job spec.
        """
        return job.spec.command

    def get_mmt_name(self, job: V1Job) -> str:
        """Return the parent multi-machine job name by stripping the machine-index suffix.

        Args:
            job: The v2 job to inspect.

        Returns:
            The parent multi-machine job name derived by removing the trailing index suffix,
            or an empty string if the job is not part of a multi-machine job.
        """
        if job.multi_machine_job_id:
            splits = job.name.rsplit("-", 1)
            if len(splits) == 2:
                return splits[0]
        return ""

    def _is_job_finished(self, job_id: str, teamspace_id: str) -> bool:
        """Return whether the job has reached a terminal state.

        Used while following logs to decide when to stop: the server keeps the log socket open
        (heartbeats only) after a job ends, so we poll the job state to detect completion.

        Args:
            job_id: The unique identifier of the job.
            teamspace_id: The ID of the teamspace that owns the job.

        Returns:
            ``True`` if the job is Completed/Failed/Stopped, else ``False`` (including when the
            state cannot be determined, so a transient status-check failure never kills a stream).
        """
        from lightning_sdk.status import Status

        try:
            job = self.get_job(job_id, teamspace_id)
        except Exception:
            # a status-check failure must not kill an active stream
            return False
        return self._job_state_to_external(job.state) in (Status.Stopped, Status.Completed, Status.Failed)

    def _job_state_to_external(self, state: str) -> "Status":
        """Convert a raw v2 job state string to the public ``Status`` enum.

        Args:
            state: The raw state string returned by the v2 jobs service.

        Returns:
            The corresponding public ``Status`` enum value, defaulting to ``Status.Pending``
            for any unrecognised state string.
        """
        from lightning_sdk.status import Status

        if state == self.v2_job_state_pending:
            return Status.Pending
        if state == self.v2_job_state_running:
            return Status.Running
        if state == self.v2_job_state_stopped:
            return Status.Stopped
        if state == self.v2_job_state_completed:
            return Status.Completed
        if state == self.v2_job_state_failed:
            return Status.Failed
        if state == self.v2_job_state_stopping:
            return Status.Stopping
        return Status.Pending

    def _get_job_machine_from_spec(self, spec: V1JobSpec, teamspace_id: str, org_id: str) -> "Machine":
        """Resolve the ``Machine`` object from a job spec by matching against available accelerators.

        Args:
            spec: The job spec containing the instance name and cluster identifier.
            teamspace_id: The ID of the teamspace used for the accelerator lookup.
            org_id: The organisation ID used for the accelerator lookup.

        Returns:
            The ``Machine`` enum value that matches the spec's instance, falling back to
            ``Machine.from_str`` if no accelerator record matches.
        """
        accelerators = self._get_machines_for_cloud_account(
            teamspace_id=teamspace_id,
            cloud_account_id=spec.cluster_id,
            org_id=org_id,
        )

        for accelerator in accelerators:
            possible_identifiers = (
                accelerator.slug,
                accelerator.slug_multi_cloud,
                accelerator.instance_id,
            )
            if (spec.instance_name and spec.instance_name in possible_identifiers) or (
                spec.instance_type and spec.instance_type in possible_identifiers
            ):
                return Machine._from_accelerator(accelerator)

        return Machine.from_str(spec.instance_name or spec.instance_type)

    def _get_machines_for_cloud_account(
        self, teamspace_id: str, cloud_account_id: str, org_id: str
    ) -> List[V1ClusterAccelerator]:
        """Return only the enabled accelerators for a given cloud account.

        Args:
            teamspace_id: The ID of the teamspace used for the accelerator lookup.
            cloud_account_id: The cloud account whose accelerators are queried.
            org_id: The organisation ID used for the accelerator lookup.

        Returns:
            A list of ``V1ClusterAccelerator`` objects that are marked as enabled.
        """
        from lightning_sdk.api.cloud_account_api import CloudAccountApi

        cloud_account_api = CloudAccountApi()
        accelerators = cloud_account_api.list_cloud_account_accelerators(
            teamspace_id=teamspace_id,
            cloud_account_id=cloud_account_id,
            org_id=org_id,
        )
        if not accelerators:
            return []

        return list(filter(lambda acc: acc.enabled, accelerators.accelerator))

    def get_total_cost(self, job: V1Job) -> float:
        """Return the accumulated cost for a v2 job in USD.

        Args:
            job: The v2 job whose cost is retrieved.

        Returns:
            The total cost incurred by the job, expressed in US dollars.
        """
        return job.total_cost
