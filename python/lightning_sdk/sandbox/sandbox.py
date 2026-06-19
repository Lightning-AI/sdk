from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from lightning_sdk.api.sandbox_api import SandboxApi
from lightning_sdk.sandbox.base import (
    ListSandboxesResult,
    SandboxInstance,
    SnapshotInfo,
    _configure_globals,
    _global_config,
    _resolve_sandbox_api,
    create_sandbox,
)
from lightning_sdk.sandbox.config import SandboxConfig
from lightning_sdk.sandbox.network_policy import NetworkPolicyInput

if TYPE_CHECKING:
    from lightning_sdk.teamspace import Teamspace


def _resolve_teamspace_id(teamspace: str | Teamspace | None) -> str | None:
    """Resolve a public teamspace value into the backend project id."""
    if teamspace is None:
        return None

    from lightning_sdk.utils.resolve import _resolve_teamspace

    if isinstance(teamspace, str) and "/" in teamspace:
        owner, teamspace_name = teamspace.split("/", 1)
        try:
            resolved = _resolve_teamspace(teamspace_name, org=owner, user=None)
        except Exception:
            resolved = _resolve_teamspace(teamspace_name, org=None, user=owner)
    else:
        resolved = _resolve_teamspace(teamspace=teamspace, org=None, user=None)

    if resolved is None:
        raise ValueError(f"Could not resolve Teamspace {teamspace!r}.")
    return resolved.id


def _sandbox_create_impl(
    *,
    sandbox_api: SandboxApi | None = None,
    config: SandboxConfig | None = None,
    name: str | None = None,
    instance_type: str | None = None,
    runtime: str | None = None,
    spot: bool = False,
    ports: list[int | str] | None = None,
    teamspace: str | Teamspace | None = None,
    snapshot_id: str | None = None,
    persistent: bool | None = None,
    network_policy: NetworkPolicyInput | None = None,
    storage_gb: int | None = None,
    timeout: int | None = None,
) -> SandboxInstance:
    if sandbox_api is not None and config is not None:
        raise ValueError("Pass only one of 'config' and sandbox_api (internal)")
    # When neither is given, fall back to the process-wide client so that
    # Sandbox.configure(api_key=..., base_url=...) defaults are actually honored
    # (the global client is seeded from env vars at import and updated by configure()).
    api = _resolve_sandbox_api(sandbox_api=sandbox_api, config=config)
    return create_sandbox(
        sandbox_api=api,
        name=name,
        instance_type=instance_type,
        runtime=runtime,
        spot=spot,
        ports=ports,
        project_id=_resolve_teamspace_id(teamspace),
        snapshot_id=snapshot_id,
        persistent=persistent,
        network_policy=network_policy,
        storage_gb=storage_gb,
        timeout=timeout,
    )


class _SandboxCreate:
    """``Sandbox.create`` / ``Sandbox(...).create`` — see :class:`Sandbox`."""

    def __get__(self, obj: Sandbox | None, objtype: type[Sandbox] | None) -> Callable[..., SandboxInstance]:
        def bound(**kwargs: Any) -> SandboxInstance:
            if obj is None:
                return _sandbox_create_impl(**kwargs)
            if kwargs.pop("config", None) is not None:
                raise ValueError(
                    "Do not pass config= when calling create() on a Sandbox client instance; "
                    "use Sandbox.create(config=...) instead.",
                )
            if kwargs.pop("sandbox_api", None) is not None:
                raise ValueError(
                    "Do not pass sandbox_api= when calling create() on a Sandbox client instance.",
                )
            return _sandbox_create_impl(sandbox_api=obj._api, **kwargs)

        return bound


class Sandbox:
    """Entry point for the Sandbox API.

    Construct with :class:`~lightning_sdk.sandbox.config.SandboxConfig` (or rely on env vars),
    then call :meth:`create`, :meth:`get`, :meth:`list`, or the snapshot helpers
    :meth:`get_snapshot`, :meth:`list_snapshots`, and :meth:`delete_snapshot`.
    The returned :class:`~lightning_sdk.sandbox.base.SandboxInstance` is a handle for
    commands, files, and lifecycle on that sandbox.

    Class methods :meth:`create` and :meth:`configure` are also available without
    constructing a client first (mirrors other Lightning SDKs).
    """

    create = _SandboxCreate()

    def __init__(self, config: SandboxConfig | None = None) -> None:
        if config is not None:
            # Explicit config gets its own isolated client.
            self._config = config
            self._api = config.api()
        else:
            # No explicit config: share the process-wide client so that
            # Sandbox.configure(api_key=..., base_url=...) defaults are honored on
            # this instance too (get/list/snapshot calls), matching Sandbox.create().
            # The shared client is seeded from env vars at import and updated by
            # configure(); _global_config() mirrors those values.
            self._config = _global_config()
            self._api = _resolve_sandbox_api()

    @property
    def config(self) -> SandboxConfig:
        return self._config

    @property
    def api(self) -> SandboxApi:
        return self._api

    @classmethod
    def configure(
        cls,
        config: SandboxConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Set process-wide defaults for ``Sandbox.create()`` when no ``config`` is passed."""
        _configure_globals(
            config=config,
            api_key=api_key,
            base_url=base_url,
        )

    def get(self, sandbox_id: str) -> SandboxInstance:
        v1 = self._api.get_sandbox(sandbox_id)
        return SandboxInstance._from_v1(v1, sandbox_api=self._api)

    def list(
        self,
        *,
        page_token: str | None = None,
        limit: int | None = None,
        teamspace: str | Teamspace | None = None,
    ) -> ListSandboxesResult:
        data = self._api.list_sandboxes(
            page_token=page_token,
            limit=limit,
            project_id=_resolve_teamspace_id(teamspace),
        )
        sandboxes = [SandboxInstance._from_v1(s, sandbox_api=self._api) for s in (data.sandboxes or [])]
        ts = data.total_size
        try:
            total = int(ts) if ts is not None else 0
        except (TypeError, ValueError):
            total = 0
        return ListSandboxesResult(
            sandboxes=sandboxes,
            next_page_token=data.next_page_token or "",
            previous_page_token=data.previous_page_token or "",
            total_size=total,
        )

    def get_snapshot(self, snapshot_id: str) -> SnapshotInfo:
        """Fetch snapshot metadata by id."""
        return SnapshotInfo._from_v1(self._api.get_snapshot(snapshot_id))

    def list_snapshots(
        self,
        *,
        name: str | None = None,
        page_token: str | None = None,
        limit: int | None = None,
    ) -> list[SnapshotInfo]:
        """List snapshots visible to this client's org / API key."""
        data = self._api.list_snapshots(
            name=name,
            page_token=page_token,
            limit=limit,
        )
        return [SnapshotInfo._from_v1(s) for s in (data.snapshots or [])]

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot by id."""
        self._api.delete_snapshot(snapshot_id)
