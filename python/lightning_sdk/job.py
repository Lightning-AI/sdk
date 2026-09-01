import warnings
from pathlib import PurePath
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, Optional, Tuple, TypedDict, Union, cast

from lightning_sdk.api.cloud_account_api import CloudAccountApi
from lightning_sdk.api.job_api import JobApiV2
from lightning_sdk.api.logs_api import LogsApi
from lightning_sdk.api.mmt_api import MMTApiV2
from lightning_sdk.api.utils import (
    AccessibleResource,
    _get_cloud_url,
    logs_filename,
    raise_access_error_if_not_allowed,
    resolve_logs_path,
)
from lightning_sdk.status import Status
from lightning_sdk.utils.logging import TrackCallsMeta
from lightning_sdk.utils.resolve import (
    _get_org_id,
    _resolve_default_cloud_account,
    _resolve_teamspace,
    _setup_logger,
    in_studio,
    skip_studio_setup,
)

if TYPE_CHECKING:
    from datetime import datetime

    from lightning_sdk.machine import CloudProvider, Machine
    from lightning_sdk.organization import Organization
    from lightning_sdk.studio import Studio
    from lightning_sdk.teamspace import Teamspace
    from lightning_sdk.user import User

_logger = _setup_logger(__name__)

__all__ = [
    "Job",
]

# A running job's log stream never sends a clean end-of-stream frame, so a bounded
# snapshot ("give me the logs up to now") is read until this many seconds of silence.
_RUNNING_LOGS_IDLE_TIMEOUT = 5.0


class _Logs:
    """A logs handle that is both a value and callable.

    ``job.logs`` behaves like the log text (a snapshot), so ``print(job.logs)``,
    ``job.logs.splitlines()`` and ``for line in job.logs`` all work. Calling it,
    ``job.logs(follow=True, tail=..., rank=...)``, fetches logs with options and
    returns an iterator of lines while ``follow=True``.

    Note: this is a str-like proxy, not an actual ``str`` (``isinstance(job.logs, str)``
    is ``False``), and static type checkers see ``_Logs`` rather than ``str``.
    """

    def __init__(self, fetch: Callable[..., Union[str, Iterator[str]]]) -> None:
        self._fetch = fetch
        self._cached: Optional[str] = None

    def __call__(
        self,
        *,
        follow: bool = False,
        tail: Optional[int] = None,
        rank: Optional[int] = None,
        timestamps: bool = False,
        since: Optional[str] = None,
        until: Optional[str] = None,
        query: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Union[str, Iterator[str]]:
        return self._fetch(
            follow=follow,
            tail=tail,
            rank=rank,
            timestamps=timestamps,
            since=since,
            until=until,
            query=query,
            severity=severity,
        )

    def _text(self) -> str:
        if self._cached is None:
            self._cached = cast(str, self._fetch(follow=False))
        return self._cached

    def __str__(self) -> str:
        return self._text()

    def __repr__(self) -> str:
        return repr(self._text())

    def __iter__(self) -> Iterator[str]:
        return iter(self._text().splitlines())

    def __len__(self) -> int:
        return len(self._text())

    def __contains__(self, item: object) -> bool:
        return self._text().__contains__(cast(Any, item))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _Logs):
            other = other._text()
        return self._text() == other

    __hash__ = None  # type: ignore[assignment]

    def __getattr__(self, name: str) -> Any:
        # only invoked for attributes not found normally; delegate to the log text.
        # guard private/dunder lookups to avoid recursing through _fetch/_cached.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._text(), name)


class JobDict(TypedDict):
    name: str
    command: str
    teamspace: str
    studio: Optional[str]
    image: Optional[str]
    status: Status
    machine: Union["Machine", str]
    total_cost: float


class Job(metaclass=TrackCallsMeta):
    """Submit and manage jobs on the Lightning AI Platform."""

    def __init__(
        self,
        name: str,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        *,
        _fetch_job: bool = True,
        _num_machines: int = 1,
    ) -> None:
        """Fetch already existing jobs.

        Args:
            name: the name of the job.
            teamspace: the teamspace the job is part of.
            org: the name of the organization owning the ``teamspace`` in case it is owned by an org.
                Deprecated — pass the owner as part of ``teamspace`` instead, e.g. ``teamspace="owner/teamspace"``.
            user: the name of the user owning the ``teamspace`` in case it is owned directly by a user instead
                of an org. Deprecated — pass the owner as part of ``teamspace`` instead,
                e.g. ``teamspace="owner/teamspace"``.

        Raises:
            ValueError: If the teamspace cannot be resolved from the provided arguments, or if the job is not found
                when ``_fetch_job=True``.
            PermissionError: If the user does not have access to jobs in the given teamspace.
        """
        if _num_machines < 1:
            raise ValueError("A job needs to run on at least one machine")

        resolved_teamspace = _resolve_teamspace(teamspace=teamspace, org=org, user=user)
        if resolved_teamspace is None:
            raise ValueError(
                "Cannot resolve the teamspace from provided arguments."
                f" Got teamspace={resolved_teamspace}, org={org}, user={user}."
            )
        raise_access_error_if_not_allowed(AccessibleResource.Jobs, resolved_teamspace.id)

        self._teamspace = resolved_teamspace
        self._name = name
        # Job payloads come from generated clients and may represent either job kind.
        self._job: Any = None
        self._prevent_refetch_latest = False
        self._cloud_account_api = CloudAccountApi()
        self._standalone_job_api = JobApiV2()
        self._mmt_job_api = MMTApiV2()
        self._num_machines = _num_machines
        self._logs_api = LogsApi()

        if _fetch_job:
            from lightning_sdk.lightning_cloud.openapi.rest import ApiException

            try:
                self._update_internal_job()
            except ApiException as ex:
                if ex.status == 404:
                    raise ValueError(f"Job {name} does not exist in Teamspace {resolved_teamspace.name}") from None
                raise

    @property
    def _job_api(self) -> Union[JobApiV2, MMTApiV2]:
        return self._mmt_job_api if self._num_machines > 1 else self._standalone_job_api

    def _attach_job(self, job: Any) -> None:
        """Bind a fetched job payload and sync ``num_machines`` from it."""
        from lightning_sdk.lightning_cloud.openapi import V1Job, V1MultiMachineJob

        self._job = job
        # Only a known payload type changes the machine count; anything else keeps the current one.
        if isinstance(job, V1MultiMachineJob):
            self._num_machines = job.machines if job.machines and job.machines > 1 else max(self._num_machines, 2)
        elif isinstance(job, V1Job):
            self._num_machines = 1

    @classmethod
    def run(
        cls,
        name: str,
        machine: Union["Machine", str],
        cloud: Optional[Union["CloudProvider", str]] = None,
        command: Optional[str] = None,
        studio: Union["Studio", str, None] = None,
        image: Optional[str] = None,
        teamspace: Union[str, "Teamspace", None] = None,
        org: Union[str, "Organization", None] = None,
        user: Union[str, "User", None] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: Optional[str] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        max_run_attempts: Optional[int] = None,
        reuse_snapshot: bool = True,
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
        num_machines: int = 1,
    ) -> "Job":
        """Run async workloads using a docker image or a compute environment from your studio.

        Args:
            name: The name of the job. Needs to be unique within the teamspace.
            machine: The machine type to run the job on.
            num_machines: The number of machines to run on. Defaults to one.
            command: The command to run inside your job. Required if using a studio. Optional if using an image.
                If not provided for images, will run the container entrypoint and default command.
            studio: The studio env to run the job with. Mutually exclusive with image.
                If both ``studio`` and ``image`` are left unset and this code is running inside a Studio
                (detected via the ``LIGHTNING_CLOUD_SPACE_ID`` env var), defaults to that Studio, provided
                its teamspace matches the resolved ``teamspace``.
            image: The docker image to run the job with. Mutually exclusive with studio.
            teamspace: The teamspace the job should be associated with. Defaults to the current teamspace.
                Accepts a bare name or an ``owner/teamspace`` slug.
            org: The organization owning the teamspace, if any. Defaults to the current organization.
                Deprecated — pass the owner as part of ``teamspace`` instead, e.g. ``teamspace="owner/teamspace"``.
            user: The user owning the teamspace, if any. Defaults to the current user.
                Deprecated — pass the owner as part of ``teamspace`` instead, e.g. ``teamspace="owner/teamspace"``.
            cloud: Cloud provider or cloud account to run the job on.
            env: Environment variables to set inside the job.
            interruptible: Whether the job should run on interruptible instances. Cheaper but can be preempted.
            image_credentials: Credentials secret name used to pull a private image.
            cloud_account_auth: Whether to authenticate with the cloud account to pull the image.
                Required if the registry is part of a cloud provider, such as ECR.
            entrypoint: The entrypoint of your docker container. Defaults to ``sh -c``.
                Set to an empty string to use the image's pre-defined entrypoint with a command.
                Only applicable when submitting docker jobs.
            path_mappings: Maps container paths to data-connection paths in the form
                ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>:<PATH>"}`` or ``{"<CONTAINER_PATH>": "<CONNECTION_NAME>"}``
                for the root of a connection. Only applicable when submitting docker jobs.
            max_runtime: DWS (Dynamic Workload Scheduler) reservation duration in seconds
                (e.g. some top-end GCP GPUs). Has no effect on non-DWS or interruptible
                (spot) machines. ``None`` means no reservation is requested.
            max_run_attempts: Max number of run attempts for this job. ``None`` or ``0`` means
                unset (backend default). ``1`` means a single attempt (no retries).
                ``N > 1`` allows up to ``N`` attempts.
            reuse_snapshot: Whether to reuse a Studio snapshot when multiple jobs for the same Studio are
                submitted. Turning this off may result in longer startup times. Defaults to True.
            scratch_disks: Optional mapping of scratch-disk mount paths to their sizes in GiB.
            placement_group_id: Optional placement group identifier for colocating the job.

        Returns:
            Job: The newly submitted Job instance.

        Raises:
            ValueError: If required arguments are missing or mutually exclusive arguments are both provided.
            RuntimeError: If image and studio are both provided.
        """
        from lightning_sdk.lightning_cloud.openapi.rest import ApiException
        from lightning_sdk.studio import Studio

        cloud_account = _resolve_default_cloud_account(None)
        if cloud is not None:
            cloud_account = None

        if not name:
            raise ValueError("A job needs to have a name!")
        if num_machines < 1:
            raise ValueError("A job needs to run on at least one machine")
        if num_machines > 1 and scratch_disks:
            raise ValueError("scratch_disks are not supported for multi-machine jobs")
        if num_machines > 1 and max_run_attempts:
            raise ValueError("max_run_attempts is not supported for multi-machine jobs")

        if image is None:
            if not isinstance(studio, Studio):
                with skip_studio_setup():
                    studio = Studio(
                        name=studio,
                        teamspace=teamspace,
                        org=org,
                        user=user,
                        cloud=cloud,
                        create_ok=False,
                    )

            if teamspace is None:
                teamspace = studio.teamspace
            else:
                teamspace_name = teamspace if isinstance(teamspace, str) else teamspace.name
                if studio.teamspace.name != teamspace_name:
                    raise ValueError(
                        "Studio teamspace does not match provided teamspace. "
                        "Can only run jobs with Studio envs in the teamspace of that Studio."
                    )

            if cloud_account is None:
                cloud_account = studio.cloud_account

            if cloud_account != studio.cloud_account:
                raise ValueError(
                    "Studio cloud account does not match provided cloud account. "
                    "Can only run jobs with Studio envs in the same cloud account."
                )

            if image_credentials is not None:
                raise ValueError("image_credentials is only supported when using a custom image")

            if cloud_account_auth:
                raise ValueError("cloud_account_auth is only supported when using a custom image")

            if entrypoint is not None:
                raise ValueError("Specifying the entrypoint has no effect for jobs with Studio envs.")

        else:
            if studio is not None:
                raise RuntimeError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )
            if cloud_account is None and cloud is None and in_studio():
                try:
                    with skip_studio_setup():
                        resolve_studio = Studio(teamspace=teamspace, user=user, org=org)
                    cloud_account = resolve_studio.cloud_account
                except (ValueError, ApiException):
                    warnings.warn("Could not infer cloud account from studio. Using teamspace default.")

            if command is not None and entrypoint is None:
                entrypoint = "sh -c"
            elif entrypoint == "" or entrypoint is None:
                entrypoint = None

        job = cls(name=name, teamspace=teamspace, org=org, user=user, _fetch_job=False, _num_machines=num_machines)
        submit_cloud = cloud if cloud_account is None else None

        job._submit(
            num_machines=num_machines,
            machine=machine,
            cloud=submit_cloud,
            command=command,
            studio=studio,
            image=image,
            env=env,
            interruptible=interruptible,
            cloud_account=cloud_account,
            image_credentials=image_credentials,
            cloud_account_auth=cloud_account_auth,
            entrypoint=entrypoint,
            path_mappings=path_mappings,
            max_runtime=max_runtime,
            max_run_attempts=max_run_attempts,
            reuse_snapshot=reuse_snapshot,
            scratch_disks=scratch_disks,
            placement_group_id=placement_group_id,
        )

        _logger.info(f"Job was successfully launched. View it at {job.link}")
        return job

    def _submit(
        self,
        machine: Union["Machine", str],
        cloud: Optional[Union["CloudProvider", str]] = None,
        command: Optional[str] = None,
        studio: Optional["Studio"] = None,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        interruptible: bool = False,
        cloud_account: Optional[str] = None,
        image_credentials: Optional[str] = None,
        cloud_account_auth: bool = False,
        entrypoint: Optional[str] = None,
        path_mappings: Optional[Dict[str, str]] = None,
        max_runtime: Optional[int] = None,
        max_run_attempts: Optional[int] = None,
        reuse_snapshot: bool = True,
        scratch_disks: Optional[Dict[str, int]] = None,
        placement_group_id: Optional[str] = None,
        num_machines: int = 1,
    ) -> "Job":
        if num_machines < 1:
            raise ValueError("A job needs to run on at least one machine")
        if num_machines > 1 and scratch_disks:
            raise ValueError("scratch_disks are not supported for multi-machine jobs")
        if num_machines > 1 and max_run_attempts:
            raise ValueError("max_run_attempts is not supported for multi-machine jobs")

        if studio is not None:
            studio_id = studio._studio.id
            if image is not None:
                raise ValueError(
                    "image and studio are mutually exclusive as both define the environment to run the job in"
                )
            if command is None:
                raise ValueError("command is required when using a studio")
        else:
            studio_id = None
            if image is None:
                raise ValueError("either image or studio must be provided")

        cloud_account = self._cloud_account_api.resolve_cloud_account(
            self._teamspace.id,
            cloud=cloud or cloud_account,
            default_cloud_account=self._teamspace.default_cloud_account,
        )

        if max_runtime:
            self._standalone_job_api.warn_if_max_runtime_noop(
                max_runtime=max_runtime,
                machine=machine,
                interruptible=interruptible,
                teamspace_id=self._teamspace.id,
                cloud_account_id=cloud_account,
                org_id=_get_org_id(self._teamspace),
                stacklevel=4,
            )

        if scratch_disks:
            if studio is None:
                raise ValueError("scratch_disks are only supported within a studio job")

            if len(scratch_disks) > 5:
                raise ValueError("scratch_disk may only contain up to 5 elements")

            for raw_path, size in scratch_disks.items():
                if size > 50000:
                    raise ValueError("scratch_disk size cannot exceed 50TiB")

                path = PurePath(raw_path)
                if path.is_absolute():
                    try:
                        path.relative_to("/teamspace/scratch")
                    except ValueError:
                        raise ValueError("scratch_disk paths must be relative to /teamspace/scratch") from None

                if ".." in path.parts:
                    raise ValueError("scratch_disk path cannot contain '..'")

        self._num_machines = num_machines
        extra_submit_kwargs: Dict[str, Any] = {}
        if num_machines <= 1:
            extra_submit_kwargs["max_run_attempts"] = max_run_attempts
        submitted = self._job_api.submit_job(
            name=self.name,
            command=command,
            cloud_account=cloud_account,
            teamspace_id=self._teamspace.id,
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
            placement_group_id=placement_group_id,
            num_machines=num_machines,
            scratch_disks=scratch_disks,
            **extra_submit_kwargs,
        )
        if num_machines <= 1 and submitted.name != self._name:
            warnings.warn(
                f"Job name '{self._name}' was already taken in this teamspace; "
                f"the job was created as '{submitted.name}' instead.",
                stacklevel=2,
            )

        self._attach_job(submitted)
        self._name = submitted.name
        return self

    def stop(self) -> None:
        if self.status in (Status.Stopped, Status.Completed, Status.Failed):
            return

        self._job_api.stop_job(job_id=self._guaranteed_job.id, teamspace_id=self._teamspace.id)

    def delete(self) -> None:
        cloudspace_id = None if self.is_multi_machine else self._guaranteed_job.spec.cloudspace_id
        self._job_api.delete_job(
            job_id=self._guaranteed_job.id,
            teamspace_id=self._teamspace.id,
            cloudspace_id=cloudspace_id,
        )

    def wait(self, interval: float = 5.0, timeout: Optional[float] = None, stop_on_timeout: bool = False) -> None:
        import time

        start = time.time()
        while True:
            if self.status in (Status.Completed, Status.Stopped, Status.Failed):
                break

            if timeout is not None and time.time() - start > timeout:
                if stop_on_timeout:
                    self.stop()
                raise TimeoutError("Job didn't finish within the provided timeout.")

            time.sleep(interval)

    async def async_wait(
        self, interval: float = 5.0, timeout: Optional[float] = None, stop_on_timeout: bool = False
    ) -> None:
        import asyncio

        start = asyncio.get_event_loop().time()
        while True:
            if self.status in (Status.Completed, Status.Stopped, Status.Failed):
                break

            if timeout is not None and asyncio.get_event_loop().time() - start > timeout:
                if stop_on_timeout:
                    self.stop()
                raise TimeoutError("Job didn't finish within the provided timeout.")

            await asyncio.sleep(interval)

    @property
    def status(self) -> Status:
        try:
            return self._job_api._job_state_to_external(self._latest_job.state)
        except Exception:
            raise RuntimeError(
                f"Job {self._name} does not exist in Teamspace {self.teamspace.name}. Did you delete it?"
            ) from None

    @property
    def started_at(self) -> Optional["datetime"]:
        """When the job started running, or ``None`` if it hasn't started yet."""
        job = self._latest_job
        if self.is_multi_machine:
            status = getattr(job, "status", None)
            return status.started_at if status is not None else None
        return getattr(job, "started_at", None)

    @property
    def stopped_at(self) -> Optional["datetime"]:
        """When the job stopped running, or ``None`` if it hasn't stopped yet."""
        job = self._latest_job
        if self.is_multi_machine:
            status = getattr(job, "status", None)
            return status.stopped_at if status is not None else None
        return getattr(job, "stopped_at", None)

    @property
    def machine(self) -> Union["Machine", str]:
        return self._job_api._get_job_machine_from_spec(
            self._guaranteed_job.spec,
            self.teamspace.id,
            _get_org_id(self.teamspace),
        )

    @property
    def public_ip(self) -> Optional[str]:
        if self.is_multi_machine:
            return None
        try:
            return self._job.public_ip_address
        except AttributeError:
            return None

    @property
    def id(self) -> Optional[str]:
        """The job's unique identifier."""
        return self._job.id if self._job is not None else None

    @property
    def resource_id(self) -> Optional[str]:
        return self.id

    @property
    def private_ip_address(self) -> Optional[str]:
        if self.is_multi_machine:
            return None
        return self._guaranteed_job.private_ip_address

    @property
    def placement_group_id(self) -> Optional[str]:
        return self._guaranteed_job.spec.placement_group_id

    @property
    def max_run_attempts(self) -> Optional[int]:
        """Max number of run attempts for this job, or ``None`` if unset."""
        spec = getattr(self._guaranteed_job, "spec", None)
        value = getattr(spec, "max_run_attempts", None)
        return value or None

    @property
    def current_run_attempt(self) -> Optional[int]:
        """Current run attempt for this job, or ``None`` if unset."""
        spec = getattr(self._guaranteed_job, "spec", None)
        value = getattr(spec, "current_run_attempt", None)
        return value or None

    @property
    def rank(self) -> Optional[int]:
        if self.is_multi_machine:
            return None
        return self._guaranteed_job.spec.rank

    @property
    def is_multi_machine(self) -> bool:
        """Whether this object represents a multi-machine parent job."""
        return self._num_machines > 1

    @property
    def num_machines(self) -> int:
        """The number of machines allocated to this job."""
        return self._num_machines

    @property
    def machines(self) -> Tuple["Job", ...]:
        """The rank-ordered machines in this job."""
        if not self.is_multi_machine:
            return (self,)

        subjobs = sorted(
            self._job_api.list_mmt_subjobs(self._guaranteed_job.id, self.teamspace.id),
            key=lambda job: job.spec.rank,
        )
        machines = []
        for subjob in subjobs:
            job = Job(name=subjob.name, teamspace=self.teamspace, _fetch_job=False, _num_machines=1)
            job._attach_job(subjob)
            machines.append(job)
        return tuple(machines)

    @property
    def artifact_path(self) -> Optional[str]:
        if self.is_multi_machine:
            raise NotImplementedError
        if self._guaranteed_job.spec.image != "":
            if self._guaranteed_job.spec.artifacts_destination:
                (
                    connection_type,
                    connection_name,
                    connection_path,
                ) = self._guaranteed_job.spec.artifacts_destination.split(":")
                return f"/teamspace/{connection_type}_connections/{connection_name}/{connection_path}"
            return None

        return f"/teamspace/jobs/{self._guaranteed_job.name}/artifacts"

    @property
    def snapshot_path(self) -> Optional[str]:
        if self.is_multi_machine:
            raise NotImplementedError
        if self._guaranteed_job.spec.image != "":
            return None
        return f"/teamspace/jobs/{self._guaranteed_job.name}/snapshot"

    @property
    def share_path(self) -> Optional[str]:
        if self.is_multi_machine:
            return None
        raise NotImplementedError("Not implemented yet")

    @property
    def logs(self) -> _Logs:
        """The job's logs.

        Use it as a value for a snapshot of the logs up to now::

            print(job.logs)

        or call it to pass options and/or follow the logs live::

            recent = job.logs(tail=100)            # snapshot of the last 100 lines
            for line in job.logs(follow=True):     # stream new lines as they arrive
                print(line)

        Options:

        - ``follow``: Keep the stream open and yield new lines as they are produced.
          Returns an iterator of lines instead of a string.
        - ``tail``: Only include the last N lines.
        - ``rank``: Distributed job rank to read from (running jobs only).
        - ``timestamps``: Prepend each line with its ISO-8601 timestamp.
        - ``since``/``until``: Only include lines within this RFC3339 time range.
        - ``query``: Only include lines containing every whitespace-separated term.
        - ``severity``: Only include lines at or above this level (``error``, ``warning``,
          ``info`` or ``debug``).

        ``since``, ``until``, ``query`` and ``severity`` are applied by the server, to both the
        saved logs and the live stream.

        A job whose lines are not in the logs API falls back to its saved log file, which
        cannot be filtered server-side. ``timestamps`` still works there, but ``query`` and
        ``severity`` raise :class:`RuntimeError` rather than silently returning nothing —
        read unfiltered and filter locally for such a job.
        """
        return _Logs(self._compute_logs)

    def download_logs(
        self,
        *,
        timestamps: bool = False,
    ) -> str:
        """Download the job's complete stored logs to a file and return the written path."""
        job = self._guaranteed_job
        cloudspace_id = None if self.is_multi_machine else job.spec.cloudspace_id
        text = self._standalone_job_api.download_logs(
            job_id=job.id,
            teamspace_id=self.teamspace.id,
            deployment_id=getattr(job, "deployment_id", None) or None,
            cloudspace_id=cloudspace_id,
            timestamps=timestamps,
        )
        dest = resolve_logs_path(None, logs_filename("job", self.name))
        dest.write_text(text, encoding="utf-8")
        return str(dest)

    def _compute_logs(
        self,
        *,
        follow: bool = False,
        tail: Optional[int] = None,
        rank: Optional[int] = None,
        timestamps: bool = False,
        since: Optional[str] = None,
        until: Optional[str] = None,
        query: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Union[str, Iterator[str]]:
        """Fetch the logs, dispatching on job state. See :attr:`logs` for the public API."""
        if self.is_multi_machine:
            return self._compute_multi_machine_logs(
                follow=follow,
                tail=tail,
                rank=rank,
                timestamps=timestamps,
                since=since,
                until=until,
                query=query,
                severity=severity,
            )

        status = self.status

        if rank is not None:
            # Reading one machine of a multi-machine job has no equivalent on the logs API, so a
            # ranked read stays on the older per-job log path.
            return self._compute_logs_ranked(status=status, follow=follow, tail=tail, rank=rank, timestamps=timestamps)

        if status not in (Status.Running, Status.Failed, Status.Completed, Status.Stopped):
            raise RuntimeError(f"Logs are not available while the job is {status}.")

        # Live-follow only makes sense while the job is running. For a finished job there is
        # nothing more to stream, so we return the saved lines rather than opening a websocket
        # that would never receive anything (and would reconnect forever).
        if follow and status == Status.Running:
            return self._stream_entries(follow=True, tail=tail, timestamps=timestamps, query=query, severity=severity)

        lines = list(
            self._stream_entries(follow=False, tail=tail, timestamps=timestamps, query=query, severity=severity)
        )
        if not lines and status != Status.Running:
            if query is not None or severity is not None:
                # An empty filtered read is ambiguous: either the filter genuinely matched
                # nothing, or this job's lines aren't in the logs API at all. Only the
                # latter needs the saved-file fallback, which cannot filter — so probe
                # unfiltered before deciding, rather than reporting "no matches" for a
                # filter that was never applied.
                if not any(self._stream_entries(follow=False, tail=1, timestamps=False)):
                    raise RuntimeError(
                        "This job's logs are only available as a saved file, which cannot be "
                        "filtered server-side, so `query`/`severity` cannot be applied. Read "
                        "the logs without them and filter locally."
                    )
                return iter(()) if follow else ""
            # Nothing in the current log format for this job: fall back to the saved log file.
            text = self._standalone_job_api.get_logs_finished(
                job_id=self._guaranteed_job.id, teamspace_id=self.teamspace.id, timestamps=timestamps
            )
            if tail is not None:
                text = "\n".join(text.splitlines()[-tail:])
            return iter(text.splitlines()) if follow else text

        # `follow` on an already-finished job returns the saved lines as an iterator (and stops),
        # keeping the return type consistent with the live-follow path.
        return iter(lines) if follow else "\n".join(lines)

    def _compute_multi_machine_logs(
        self,
        *,
        follow: bool,
        tail: Optional[int],
        rank: Optional[int],
        timestamps: bool,
        since: Optional[str],
        until: Optional[str],
        query: Optional[str],
        severity: Optional[str],
    ) -> Union[str, Iterator[str]]:
        if rank is not None:
            raise ValueError(
                "`rank` is not supported on a multi-machine parent; "
                "read a single machine with `job.machines[rank].logs` "
                "(or `mmt.machines[rank].logs` through the compatibility API)."
            )

        status = self.status
        if status not in (Status.Running, Status.Failed, Status.Completed, Status.Stopped):
            raise RuntimeError(f"Logs are not available while the job is {status}.")

        lines = self._stream_multi_machine_entries(
            follow=follow and status == Status.Running,
            tail=tail,
            timestamps=timestamps,
            since=since,
            until=until,
            query=query,
            severity=severity,
        )
        if follow and status == Status.Running:
            return lines
        collected = list(lines)
        return iter(collected) if follow else "\n".join(collected)

    def _stream_multi_machine_entries(
        self,
        *,
        follow: bool,
        tail: Optional[int],
        timestamps: bool,
        since: Optional[str],
        until: Optional[str],
        query: Optional[str],
        severity: Optional[str],
    ) -> Iterator[str]:
        names = {machine._guaranteed_job.id: machine.name for machine in self.machines}
        entries = self._logs_api.stream(
            self.teamspace.id,
            mmt_id=self._guaranteed_job.id,
            since=since,
            until=until,
            query=query,
            severity=severity,
            follow=follow,
            tail=tail,
            tail_anchor=getattr(self._guaranteed_job, "stopped_at", None),
            idle_timeout=None if follow else _RUNNING_LOGS_IDLE_TIMEOUT,
            fallback_to_live=not follow,
            stop=lambda: self.status in (Status.Stopped, Status.Completed, Status.Failed),
        )
        for entry in entries:
            yield entry.format(timestamps=timestamps, prefix=names.get(entry.resource_id, entry.resource_id))

    def _compute_logs_ranked(
        self,
        *,
        status: Status,
        follow: bool,
        tail: Optional[int],
        rank: int,
        timestamps: bool,
    ) -> Union[str, Iterator[str]]:
        """Read a single machine's logs over the legacy per-job websocket."""
        if status in (Status.Failed, Status.Completed, Status.Stopped):
            warnings.warn(
                "`rank` is only supported for running jobs; ignoring it for finished-job logs.",
                stacklevel=3,
            )
            text = self._standalone_job_api.get_logs_finished(
                job_id=self._guaranteed_job.id, teamspace_id=self.teamspace.id, timestamps=timestamps
            )
            if tail is not None:
                text = "\n".join(text.splitlines()[-tail:])
            return iter(text.splitlines()) if follow else text

        if status != Status.Running:
            raise RuntimeError(f"Logs are not available while the job is {status}.")

        if follow:
            return self._stream_logs(follow=True, tail=tail, rank=rank, timestamps=timestamps)

        # a running job's stream has no clean end signal, so read until it goes idle
        text = "\n".join(
            self._stream_logs(
                follow=False,
                tail=tail,
                rank=rank,
                timestamps=timestamps,
                idle_timeout=_RUNNING_LOGS_IDLE_TIMEOUT,
            )
        )
        if tail is not None:
            text = "\n".join(text.splitlines()[-tail:])
        return text

    def _stream_entries(
        self,
        *,
        follow: bool,
        tail: Optional[int],
        timestamps: bool,
        since: Optional[str] = None,
        until: Optional[str] = None,
        query: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Iterator[str]:
        """Yield formatted log lines from the logs API (saved logs, then the live tail)."""
        job = self._guaranteed_job
        job_id = job.id
        entries = self._logs_api.stream(
            self.teamspace.id,
            job_ids=[job_id],
            since=since,
            until=until,
            query=query,
            severity=severity,
            follow=follow,
            tail=tail,
            # A finished job's last lines sit at its stop time, so start the tail search there
            # instead of walking back from now through a job that ran days ago.
            tail_anchor=getattr(job, "stopped_at", None),
            idle_timeout=None if follow else _RUNNING_LOGS_IDLE_TIMEOUT,
            # A running job whose logs are not in the current storage format yet has no saved
            # history; tail its live stream so a snapshot still shows something.
            fallback_to_live=not follow,
            stop=lambda: self._standalone_job_api._is_job_finished(job_id, self.teamspace.id),
        )
        for entry in entries:
            yield entry.format(timestamps=timestamps)

    def _stream_logs(
        self,
        *,
        follow: bool = True,
        tail: Optional[int] = None,
        rank: Optional[int] = None,
        idle_timeout: Optional[float] = None,
        timestamps: bool = False,
    ) -> Iterator[str]:
        """Stream the job's logs live over the websocket (internal; see :attr:`logs`)."""
        return self._standalone_job_api.stream_logs(
            job_id=self._guaranteed_job.id,
            teamspace_id=self.teamspace.id,
            follow=follow,
            tail=tail,
            rank=rank,
            idle_timeout=idle_timeout,
            timestamps=timestamps,
        )

    @property
    def link(self) -> str:
        if self.is_multi_machine:
            return f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/jobs/{self.name}?app_id=mmt"

        mmt_name = self._standalone_job_api.get_mmt_name(self._guaranteed_job)

        if self._job_api.get_image_name(self._guaranteed_job):
            if mmt_name:
                return (
                    f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/"
                    f"jobs/{mmt_name}?app_id=mmt&machine_name={self.name}"
                )
            return f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/jobs/{self.name}?app_id=jobs"

        studio_name = self._job_api.get_studio_name(self._guaranteed_job)
        if not studio_name:
            raise RuntimeError("Cannot extract studio name from job")
        return (
            f"{_get_cloud_url()}/{self.teamspace.owner.name}/{self.teamspace.name}/studios/"
            f"{studio_name}/app?app_id=jobs&job_name={self.name}"
        )

    @property
    def image(self) -> Optional[str]:
        return self._job_api.get_image_name(self._guaranteed_job)

    @property
    def studio_name(self) -> Optional[str]:
        """The name of the studio this job runs in, without instantiating the Studio."""
        return self._job_api.get_studio_name(self._guaranteed_job)

    @property
    def studio(self) -> Optional["Studio"]:
        from lightning_sdk.studio import Studio

        studio_name = self._job_api.get_studio_name(self._guaranteed_job)
        if not studio_name:
            return None
        return Studio(studio_name, teamspace=self.teamspace)

    @property
    def command(self) -> str:
        return self._job_api.get_command(self._guaranteed_job)

    def _update_internal_job(self) -> None:
        if getattr(self, "_job", None) is None:
            if self.is_multi_machine:
                self._attach_job(self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id))
                return

            from lightning_sdk.lightning_cloud.openapi.rest import ApiException

            try:
                self._attach_job(
                    self._standalone_job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id)
                )
            except ApiException as ex:
                if ex.status != 404:
                    raise
                # Switch to the multi-machine API, then sync the real machine count from the payload.
                self._num_machines = 2
                self._attach_job(self._job_api.get_job_by_name(name=self._name, teamspace_id=self._teamspace.id))
            return

        self._attach_job(self._job_api.get_job(job_id=self._job.id, teamspace_id=self._teamspace.id))

    @property
    def name(self) -> str:
        return self._name

    @property
    def teamspace(self) -> "Teamspace":
        return self._teamspace

    def dict(self) -> JobDict:
        studio = self.studio

        return {
            "name": self.name,
            "teamspace": f"{self.teamspace.owner.name}/{self.teamspace.name}",
            "studio": studio.name if studio else None,
            "image": self.image,
            "command": self.command,
            "status": self.status,
            "machine": self.machine,
            "total_cost": self.total_cost,
        }

    def json(self) -> str:
        import json

        return json.dumps(self.dict(), indent=4, sort_keys=True, default=str)

    @property
    def _guaranteed_job(self) -> Any:
        if getattr(self, "_job", None) is None:
            self._update_internal_job()

        return self._job

    @property
    def total_cost(self) -> float:
        return self._job_api.get_total_cost(self._latest_job)

    @property
    def _latest_job(self) -> Any:
        if self._prevent_refetch_latest:
            return self._guaranteed_job

        self._update_internal_job()
        return self._job
