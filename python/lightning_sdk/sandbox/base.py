from __future__ import annotations

import shlex
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from lightning_sdk.api.sandbox_api import CommandLog, CommandStatus, SandboxApi, raise_sandbox_api_error
from lightning_sdk.lightning_cloud.openapi import (
    SandboxesServiceApi,
    SandboxesServiceCreateSandboxSnapshotBody,
    SandboxesServiceStopSandboxBody,
    SandboxesServiceUpdateSandboxBody,
    SandboxesServiceWriteSandboxFileBody,
    V1CreateSandboxRequest,
    V1Sandbox,
    V1SandboxSnapshot,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.machine import Machine
from lightning_sdk.sandbox.command import Command
from lightning_sdk.sandbox.config import SandboxConfig
from lightning_sdk.sandbox.network_policy import NetworkPolicyInput, to_v1_network_policy
from lightning_sdk.utils.logging import TrackCallsMeta

if TYPE_CHECKING:
    from lightning_sdk.sandbox.filesystem import FileSystem
    from lightning_sdk.sandbox.process import SandboxProcess

_sandbox_config: dict[str, Any] = {}
_sandbox_config.update(SandboxConfig.from_env().to_api_dict())
_api = SandboxApi(_sandbox_config)


def _resolve_sandbox_api(
    *,
    sandbox_api: SandboxApi | None = None,
    config: SandboxConfig | None = None,
) -> SandboxApi:
    if sandbox_api is not None and config is not None:
        raise ValueError("Pass only one of 'sandbox_api' and 'config'")
    if sandbox_api is not None:
        return sandbox_api
    if config is not None:
        return config.api()
    return _api


def _org_id_from_api(api: SandboxApi) -> str | None:
    """Organization UUID from client config only (env / SandboxConfig), if set."""
    org_id = api.config_get("organization_id")
    return str(org_id) if org_id else None


def _resolve_org_id(override: str | None = None, *, api: SandboxApi | None = None) -> str | None:
    if override is not None:
        return override
    if api is not None:
        return _org_id_from_api(api)
    return _org_id_from_api(_api)


def configure(
    config: SandboxConfig | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    organization_id: str | None = None,
) -> None:
    """Set global defaults for sandbox API calls.

    Pass a :class:`SandboxConfig` and/or individual fields. Later keyword arguments
    override values from ``config``. The process-wide store is also initialized from
    environment variables at import.
    """
    if config is not None:
        _sandbox_config.update(config.to_api_dict())
    if api_key is not None:
        _sandbox_config["api_key"] = api_key
    if base_url is not None:
        _sandbox_config["base_url"] = base_url
    if organization_id is not None:
        _sandbox_config["organization_id"] = organization_id
    _api.reset()


_configure_globals = configure


def _wait_until_sandbox_running(api: SandboxApi, v1: V1Sandbox) -> V1Sandbox:
    """Poll until status is ``running`` (SDK orchestration; OpenAPI calls only via ``api``)."""
    start = time.monotonic()
    deadline = start + 300.0
    org = v1.organization_id
    while v1.status != "running":
        if v1.status in ("error", "stopped", "shutdown"):
            raise RuntimeError(f"Sandbox entered terminal state: {v1.status}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Sandbox did not become ready (current status: {v1.status})")
        elapsed = time.monotonic() - start
        time.sleep(0.1 if elapsed < 5.0 else 1.0)
        v1 = api.get_sandbox(v1.id, organization_id=org or None)
    return v1


def create_sandbox(
    *,
    sandbox_api: SandboxApi,
    name: str | None = None,
    instance_type: str | None = None,
    runtime: str | None = None,
    spot: bool = False,
    ports: list[int | str] | None = None,
    cluster_id: str | None = None,
    cloudspace_id: str | None = None,
    snapshot_id: str | None = None,
    persistent: bool | None = None,
    network_policy: NetworkPolicyInput | None = None,
) -> SandboxInstance:
    """Create a sandbox and block until its status is ``running``.

    Internal: called from :class:`~lightning_sdk.sandbox.sandbox.Sandbox` with a
    client built via :meth:`~lightning_sdk.sandbox.config.SandboxConfig.api`.
    ``organization_id`` on the client is optional (``LIGHTNING_ORG_ID`` or config).

    Pass ``snapshot_id`` to restore the sandbox's filesystem from a snapshot
    (see :meth:`SandboxInstance.snapshot`) for a fast, pre-warmed start. Pass
    ``persistent=True`` so the sandbox's state survives :meth:`SandboxInstance.stop`
    (via an auto-snapshot) and can be brought back with :meth:`SandboxInstance.resume`.

    ``network_policy`` is create-time only: omit for open egress (``allow-all``),
    pass ``"deny-all"``, or a :class:`~lightning_sdk.sandbox.network_policy.NetworkPolicy`
    CIDR allowlist. Restored snapshots inherit the source policy unless overridden.
    """
    org_id = sandbox_api.config_get("organization_id")
    if org_id is not None:
        org_id = str(org_id)
    if name is None:
        name = f"sandbox-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    if instance_type is not None:
        it = instance_type
    else:
        _ = runtime  # reserved for richer runtime, machine maps later
        it = Machine.CPU_SMALL.slug

    body = V1CreateSandboxRequest(
        name=name,
        instance_type=it,
        spot=spot,
        ports=[str(p) for p in (ports or [])],
    )
    if org_id:
        body.organization_id = org_id
    if cluster_id:
        body.cluster_id = cluster_id
    if cloudspace_id:
        body.cloudspace_id = cloudspace_id
    if runtime:
        body.runtime = runtime
    if snapshot_id:
        body.snapshot_id = snapshot_id
    if persistent is not None:
        body.persistent = persistent
    v1_policy = to_v1_network_policy(network_policy)
    if v1_policy is not None:
        body.network_policy = v1_policy

    sb: SandboxesServiceApi = sandbox_api.sandboxes()
    try:
        v1 = sb.sandboxes_service_create_sandbox(body)
    except ApiException as e:
        raise_sandbox_api_error(e)
    v1 = _wait_until_sandbox_running(sandbox_api, v1)
    return SandboxInstance._from_v1(v1, runtime=runtime, sandbox_api=sandbox_api)


def _wait_for_snapshot_ready(
    api: SandboxApi,
    snapshot_id: str,
    organization_id: str | None,
    timeout: float,
) -> V1SandboxSnapshot:
    """Poll a snapshot row until it reaches ``ready`` (or ``failed``).

    The create-snapshot call returns a row in ``saving``; the control plane
    captures + uploads on a background goroutine then flips it to ``ready``.
    Poll fast early, then back off (250ms → 2s cap).
    """
    deadline = time.monotonic() + timeout
    delay = 0.25
    while True:
        snap = api.get_snapshot(snapshot_id, organization_id=organization_id)
        if snap.status == "ready":
            return snap
        if snap.status == "failed":
            raise RuntimeError(f"Snapshot {snapshot_id} entered terminal state 'failed'")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Snapshot {snapshot_id} not ready within {timeout}s (last status: {snap.status})")
        time.sleep(delay)
        delay = min(delay * 2, 2.0)


@dataclass
class RunCommandOpts:
    cmd: str
    args: list[str] | None = None
    cwd: str | None = None
    env: dict[str, str] | None = None
    sudo: bool | None = None
    detached: bool | None = None


@dataclass
class WriteFileParams:
    path: str
    content: str


@dataclass
class ListSandboxesResult:
    sandboxes: list[SandboxInstance]
    next_page_token: str
    previous_page_token: str
    total_size: int


@dataclass
class SnapshotInfo:
    """A sandbox filesystem snapshot (immutable, reusable base image)."""

    id: str
    status: str
    runtime: str
    size_bytes: int
    project_id: str

    @classmethod
    def _from_v1(cls, v1: V1SandboxSnapshot) -> SnapshotInfo:
        try:
            size = int(v1.size_bytes) if v1.size_bytes is not None else 0
        except (TypeError, ValueError):
            size = 0
        return cls(
            id=v1.id,
            status=v1.status or "",
            runtime=v1.runtime or "",
            size_bytes=size,
            project_id=v1.project_id or "",
        )


class SandboxInstance(metaclass=TrackCallsMeta):
    """A running sandbox returned by :class:`~lightning_sdk.sandbox.sandbox.Sandbox`.

    Obtain instances via ``Sandbox(config).create(...)``, ``.get(...)``, or ``.list(...)``.
    Remote sandboxes are **not** destroyed when a Python reference goes out of scope;
    call :meth:`delete` to release the sandbox explicitly.
    """

    def __init__(
        self,
        data: V1Sandbox,
        *,
        runtime: str | None = None,
        sandbox_api: SandboxApi | None = None,
    ) -> None:
        self._v1 = data
        self._runtime = runtime
        self._sandbox_api = sandbox_api or _api
        self._fs_inst: Any = None
        self._process_inst: Any = None

    @classmethod
    def _from_v1(
        cls,
        v1: V1Sandbox,
        *,
        runtime: str | None = None,
        sandbox_api: SandboxApi | None = None,
    ) -> SandboxInstance:
        return cls(v1, runtime=runtime, sandbox_api=sandbox_api or _api)

    @property
    def runtime(self) -> str | None:
        return self._runtime

    @property
    def sandbox_id(self) -> str:
        return self._v1.id

    @property
    def name(self) -> str:
        return self._v1.name

    @property
    def organization_id(self) -> str:
        return self._v1.organization_id or ""

    @property
    def project_id(self) -> str:
        """Teamspace this sandbox belongs to (set by the control plane / API key scope)."""
        return self._v1.project_id or ""

    @property
    def cluster_id(self) -> str:
        return self._v1.cluster_id or ""

    @property
    def instance_type(self) -> str:
        return self._v1.instance_type or ""

    @property
    def spot(self) -> bool:
        return bool(self._v1.spot)

    @property
    def persistent(self) -> bool:
        """Whether the sandbox's state survives :meth:`stop` via an auto-snapshot."""
        return bool(getattr(self._v1, "persistent", False))

    @property
    def status(self) -> str:
        return self._v1.status or ""

    @property
    def cloudspace_id(self) -> str:
        return self._v1.cloudspace_id or ""

    @property
    def ports(self) -> list[str]:
        return list(self._v1.ports or [])

    @property
    def created_at(self) -> datetime:
        return self._v1.created_at

    @property
    def updated_at(self) -> datetime:
        return self._v1.updated_at

    @property
    def fs(self) -> FileSystem:
        from lightning_sdk.sandbox.filesystem import FileSystem

        if self._fs_inst is None:
            self._fs_inst = FileSystem(self)
        return self._fs_inst

    @property
    def process(self) -> SandboxProcess:
        r"""Interactive process namespace for this sandbox.

        Provides PTY sessions and shell-style helpers. Mirrors Daytona's
        ``sandbox.process`` surface.

        ::

            pty = sandbox.process.create_pty(PtyCreateOpts(
                session_name="shell",
                cluster_id=sandbox.cluster_id,
                on_data=lambda chunk: sys.stdout.buffer.write(chunk),
            ))
            pty.send_input("ls -la\n")
        """
        from lightning_sdk.sandbox.process import SandboxProcess, SandboxProcessContext

        if self._process_inst is None:
            self._process_inst = SandboxProcess(
                SandboxProcessContext(
                    sandbox_id=self.sandbox_id,
                    organization_id=self.organization_id,
                    get_api_key=self._get_api_key,
                    get_base_url=self._get_base_url,
                    run_command=self._run_command_for_process,
                )
            )
        return self._process_inst

    # -- internal helpers used by the PTY namespace ---------------------------

    def _get_api_key(self) -> str:
        """Best-effort lookup of the bearer token from the OpenAPI client.

        Mirrors the lazy lookup the JS SDK performs so that
        :meth:`~lightning_sdk.sandbox.sandbox.Sandbox.configure` calls made after the sandbox object
        was created are still honored.
        """
        headers = getattr(self._sandbox_api.client.api_client, "default_headers", {})
        auth = headers.get("Authorization", "") if isinstance(headers, dict) else ""
        if isinstance(auth, str) and auth.startswith("Bearer "):
            return auth[len("Bearer ") :]
        return auth or ""

    def _get_base_url(self) -> str:
        return self._sandbox_api.host

    def _run_command_for_process(self, *, cmd: str, args: list[str] | None = None) -> Command:
        """Adapt :meth:`run_command` to the kwarg shape ``SandboxProcess`` expects.

        Avoids exposing the ``RunCommandOpts`` dataclass to the
        :class:`SandboxProcess` module, which keeps the two modules decoupled.
        """
        return self.run_command(RunCommandOpts(cmd=cmd, args=args or []))

    def delete(self) -> None:
        """Destroy the sandbox, dropping any auto-snapshot.

        For a persistent sandbox use :meth:`stop` instead if you want to
        :meth:`resume` later.
        """
        org = self._v1.organization_id
        sb: SandboxesServiceApi = self._sandbox_api.sandboxes()
        try:
            if org:
                sb.sandboxes_service_delete_sandbox(self._v1.id, organization_id=org)
            else:
                sb.sandboxes_service_delete_sandbox(self._v1.id)
        except ApiException as e:
            if e.status == 404:
                return
            raise_sandbox_api_error(e)

    def stop(self) -> str:
        """Stop the sandbox.

        For a ``persistent=True`` sandbox the control plane synchronously
        captures an auto-snapshot before tearing down the server and returns its
        id; the sandbox id keeps resolving (status ``paused``) and can be brought
        back with :meth:`resume`. For a non-persistent sandbox this is equivalent
        to :meth:`delete` and returns an empty string.
        """
        org = self._v1.organization_id
        body = SandboxesServiceStopSandboxBody()
        if org:
            body.organization_id = org
        if self._v1.project_id:
            body.project_id = self._v1.project_id
        sb: SandboxesServiceApi = self._sandbox_api.sandboxes()
        try:
            resp = sb.sandboxes_service_stop_sandbox(body, self._v1.id)
        except ApiException as e:
            raise_sandbox_api_error(e)
        return resp.auto_snapshot_id or ""

    def resume(self) -> SandboxInstance:
        """Resume a stopped persistent sandbox from its auto-snapshot.

        Preserves the sandbox id and polls until ``running``. Errors if the
        sandbox is not persistent or has no resumable snapshot.
        """
        org = self._v1.organization_id
        body = SandboxesServiceUpdateSandboxBody(resume=True)
        if org:
            body.organization_id = org
        sb: SandboxesServiceApi = self._sandbox_api.sandboxes()
        try:
            v1 = sb.sandboxes_service_update_sandbox(body, self._v1.id)
        except ApiException as e:
            raise_sandbox_api_error(e)
        self._v1 = _wait_until_sandbox_running(self._sandbox_api, v1)
        return self

    def snapshot(
        self,
        *,
        expiration: str | None = None,
        excludes: list[str] | None = None,
        wait: bool = True,
        wait_timeout: float = 600.0,
    ) -> SnapshotInfo:
        """Snapshot this sandbox's filesystem and return the :class:`SnapshotInfo`.

        The control plane pauses the sandbox, tarballs its overlay upperdir,
        resumes it, then uploads the tarball. Only filesystem state is captured —
        running processes are not preserved. By default this polls until the
        snapshot is ``ready`` so the returned object is safe to immediately
        restore from via ``Sandbox.create(snapshot_id=...)``; pass ``wait=False``
        to return the ``saving`` row without polling.
        """
        org = self.organization_id or None
        body = SandboxesServiceCreateSandboxSnapshotBody()
        if org:
            body.organization_id = org
        if self._v1.project_id:
            body.project_id = self._v1.project_id
        if expiration is not None:
            body.expiration = expiration
        if excludes:
            body.excludes = excludes
        sb: SandboxesServiceApi = self._sandbox_api.sandboxes()
        try:
            snap = sb.sandboxes_service_create_sandbox_snapshot(body, self.sandbox_id)
        except ApiException as e:
            raise_sandbox_api_error(e)
        if wait:
            snap = _wait_for_snapshot_ready(self._sandbox_api, snap.id, org, wait_timeout)
        return SnapshotInfo._from_v1(snap)

    def run_command(self, command_or_opts: str | RunCommandOpts, args: list[str] | None = None) -> Command:
        """Run a command inside the sandbox.

        Returns a :class:`~lightning_sdk.sandbox.command.Command` handle. When
        called without ``detached=True``, the server has already waited for the
        process to exit and the returned handle has :attr:`Command.exit_code`
        populated. With ``detached=True``, the call returns immediately; call
        :meth:`Command.wait` to block until completion.
        """
        org = self.organization_id or None
        detached = False
        if isinstance(command_or_opts, str):
            if args is None and " " in command_or_opts:
                try:
                    parts = shlex.split(command_or_opts)
                except ValueError:
                    parts = command_or_opts.split()
                command_or_opts = parts[0]
                args = parts[1:]
            api_result = self._sandbox_api.run_command(
                self.sandbox_id,
                command=command_or_opts,
                args=args or [],
                organization_id=org,
            )
        else:
            o = command_or_opts
            detached = bool(o.detached)
            api_result = self._sandbox_api.run_command(
                self.sandbox_id,
                command=o.cmd,
                args=o.args or [],
                organization_id=org,
                cwd=o.cwd,
                env=o.env,
                sudo=o.sudo,
                detached=o.detached,
            )

        return Command(
            self,
            cmd_id=api_result.cmd_id,
            output=api_result.output,
            exit_code=None if detached else api_result.exit_code,
        )

    def get_command_logs(self, cmd_id: str) -> list[CommandLog]:
        return self._sandbox_api.get_command_logs(self.sandbox_id, cmd_id, self.organization_id or None)

    def kill_command(self, cmd_id: str) -> None:
        self._sandbox_api.kill_command(self.sandbox_id, cmd_id, self.organization_id or None)

    def get_command(self, cmd_id: str) -> CommandStatus:
        return self._sandbox_api.get_command(self.sandbox_id, cmd_id, self.organization_id or None)

    def wait_for_command(
        self,
        cmd_id: str,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.5,
    ) -> CommandStatus:
        """Poll :meth:`get_command` until the command exits and return its final status.

        Useful after launching a background command with ``detached=True``::

            r = sandbox.run_command(RunCommandOpts(cmd="long-task", detached=True))
            status = sandbox.get_command(r.cmd_id)
            if status.running:
                final = sandbox.wait_for_command(r.cmd_id)
                print(final.exit_code)

        Args:
            cmd_id: Command identifier returned by :meth:`run_command`.
            timeout: Maximum seconds to wait. ``None`` (default) waits indefinitely.
            poll_interval: Seconds between polls.

        Raises:
            TimeoutError: If ``timeout`` elapses before the command exits.
        """
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        while True:
            status = self.get_command(cmd_id)
            if not status.running:
                return status
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for command {cmd_id} to finish")
            time.sleep(poll_interval)

    def write_file(self, path: str, content: str) -> None:
        body = SandboxesServiceWriteSandboxFileBody(path=path, content=content)
        if self.organization_id:
            body.organization_id = self.organization_id
        sb: SandboxesServiceApi = self._sandbox_api.sandboxes()
        sb.sandboxes_service_write_sandbox_file(body, self.sandbox_id)

    def read_file(self, path: str) -> str | None:
        try:
            kwargs: dict[str, Any] = {"path": path}
            if self.organization_id:
                kwargs["organization_id"] = self.organization_id
            sb: SandboxesServiceApi = self._sandbox_api.sandboxes()
            resp = sb.sandboxes_service_get_sandbox_file(self.sandbox_id, **kwargs)
            return resp.content
        except ApiException as e:
            if e.status == 404:
                return None
            if e.status == 500 and b"file not found" in (e.body or b""):
                return None
            raise

    def write_files(self, files: list[WriteFileParams]) -> None:
        for f in files:
            self.write_file(f.path, f.content)

    def mkdir(self, path: str) -> None:
        self._sandbox_api.create_directory(self.sandbox_id, path, self.organization_id or None)

    create_directory = mkdir
