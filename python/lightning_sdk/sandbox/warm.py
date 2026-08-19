"""Warm sandbox recipes (maps to ``V1SandboxWarmSpec``).

A recipe says what a sandbox should already have done by the time you get it:
packages installed, a server listening, a runtime warmed up. Lightning runs it
once, snapshots the result, and restores later sandboxes with the same recipe
from that snapshot instead of running it again.

The recipe *is* the cache key, so there is no template id to store or refresh.
The key also covers the image, the sandbox shape and the host runtime version,
so a rebuilt image invalidates it on its own and the next create bakes afresh.

    from lightning_sdk.sandbox import Sandbox, WarmRecipe, wait_for_port

    sandbox = Sandbox.create(
        instance_type="cpu-2",
        image="docker.io/library/python:3.13",
        ports=[8888],
        warm=WarmRecipe(
            run_cmd=["pip install jupyterlab"],
            start_cmd="jupyter lab --ip=0.0.0.0 --port=8888",
            ready_cmd=wait_for_port(8888),
        ),
    )
    sandbox.warm.state  # "restored" | "building" | "cold"

The first create for a recipe is served cold with the recipe run inline, so you
always get the sandbox you asked for; it is only slower. Baking happens in the
background once a recipe has been asked for more than once, and checkpoints are
per host, so expect the first creates across a cluster to report ``cold`` or
``building`` rather than a clean second-create hit.

Warm only pays when the recipe is the expensive part. For a trivial recipe,
restoring a checkpoint costs more than the boot it replaces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from lightning_sdk.lightning_cloud.openapi.models import (
    V1SandboxReadyCheck,
    V1SandboxReadyUrl,
    V1SandboxRebindVar,
    V1SandboxWarmSpec,
    V1SandboxWarmStatus,
)

#: What a sandbox did about its recipe. ``"unknown"`` covers a state this SDK
#: build predates, so a newer backend cannot break an older client.
WarmState: TypeAlias = Literal["restored", "building", "cold", "unknown"]

#: Where a per-sandbox value comes from. ``"generated-token"`` mints a fresh
#: random token for each sandbox.
RebindSource: TypeAlias = Literal["generated-token", "sandbox-id", "hostname"]

_REBIND_SOURCES: dict[str, str] = {
    "generated-token": "SANDBOX_REBIND_SOURCE_GENERATED_TOKEN",
    "sandbox-id": "SANDBOX_REBIND_SOURCE_SANDBOX_ID",
    "hostname": "SANDBOX_REBIND_SOURCE_HOSTNAME",
}

_WARM_STATES: dict[str, WarmState] = {
    "SANDBOX_WARM_STATE_RESTORED": "restored",
    "SANDBOX_WARM_STATE_BUILDING": "building",
    "SANDBOX_WARM_STATE_COLD": "cold",
}


@dataclass(frozen=True)
class ReadyCheck:
    """When the recipe is finished and the sandbox is worth snapshotting.

    Build one with :func:`wait_for_port`, :func:`wait_for_url`,
    :func:`wait_for_process`, :func:`wait_for_file` or :func:`wait_for_timeout`
    rather than constructing it directly. Exactly one field is set.
    """

    port: int | None = None
    url: str | None = None
    url_status: int | None = None
    process: str | None = None
    file: str | None = None
    timeout_ms: int | None = None
    exec: str | None = None

    def to_v1(self) -> V1SandboxReadyCheck:
        if self.port is not None:
            return V1SandboxReadyCheck(port=self.port)
        if self.url is not None:
            return V1SandboxReadyCheck(url=V1SandboxReadyUrl(url=self.url, status_code=self.url_status))
        if self.process is not None:
            return V1SandboxReadyCheck(process=self.process)
        if self.file is not None:
            return V1SandboxReadyCheck(file=self.file)
        if self.timeout_ms is not None:
            return V1SandboxReadyCheck(timeout_ms=self.timeout_ms)
        return V1SandboxReadyCheck(_exec=self.exec)


def wait_for_port(port: int) -> ReadyCheck:
    """Ready once something is listening on this TCP port inside the sandbox."""
    return ReadyCheck(port=port)


def wait_for_url(url: str, status_code: int | None = None) -> ReadyCheck:
    """Ready once this URL, resolved from inside the sandbox, answers.

    Defaults to expecting ``200``. Note that an endpoint behind authentication
    answers ``403`` until you authenticate, so a port check is often the more
    honest signal for a server that requires a token.
    """
    return ReadyCheck(url=url, url_status=status_code)


def wait_for_process(name: str) -> ReadyCheck:
    """Ready once a process with this name is running."""
    return ReadyCheck(process=name)


def wait_for_file(path: str) -> ReadyCheck:
    """Ready once this path exists inside the sandbox."""
    return ReadyCheck(file=path)


def wait_for_timeout(milliseconds: int) -> ReadyCheck:
    """Ready after a fixed wait — the blunt option when nothing is observable.

    Honoured only when no other check is set: a bare sleep must never shadow a
    real probe.
    """
    return ReadyCheck(timeout_ms=milliseconds)


def wait_for_command(command: str) -> ReadyCheck:
    """Ready once this shell command exits 0."""
    return ReadyCheck(exec=command)


@dataclass(frozen=True)
class RebindVar:
    """A value that must differ per sandbox despite the shared snapshot.

    The bake runs against ``bake_value``, so a credential-bearing process starts
    against a placeholder and no live credential is ever captured in the shared
    snapshot. Lightning materializes the real value at restore, exports it to
    ``after_restore_cmd``, writes it to ``/run/lightning/warm/<name>``, and
    returns it once in :attr:`SandboxInstance.warm_secrets`.

    ``bake_value`` is required for ``"generated-token"``: the real value cannot
    exist until a sandbox does.
    """

    name: str
    source: RebindSource = "generated-token"
    bake_value: str | None = None

    def to_v1(self) -> V1SandboxRebindVar:
        try:
            source = _REBIND_SOURCES[self.source]
        except KeyError:
            raise ValueError(
                f"rebind source must be one of {sorted(_REBIND_SOURCES)}, got {self.source!r}",
            ) from None
        return V1SandboxRebindVar(name=self.name, source=source, bake_value=self.bake_value)


@dataclass(frozen=True)
class WarmRecipe:
    """What a sandbox should already have done when you get it.

    ``run_cmd`` runs first, then ``start_cmd``, then — once ``ready_cmd``
    passes — ``after_start_cmd``. All of it happens at bake time; a restored
    sandbox observes the effects without re-running anything.

    ``after_start_cmd`` is the one that needs the server: it is the only place a
    recipe can warm something that does not exist until ``start_cmd`` is up,
    such as a Jupyter kernel. ``run_cmd`` cannot, because nothing is listening
    when it runs.
    """

    #: Setup commands, in order. Bake-time only.
    run_cmd: list[str] = field(default_factory=list)
    #: The long-running process to leave running in the snapshot.
    start_cmd: str | None = None
    #: Commands run once ``start_cmd`` is up and ``ready_cmd`` has passed.
    after_start_cmd: list[str] = field(default_factory=list)
    #: When to snapshot. Defaults to a TCP listen check on the first declared
    #: port, or to ``start_cmd`` exiting 0 when no ports are declared.
    ready_cmd: ReadyCheck | None = None
    #: How long to keep retrying ``ready_cmd``. Defaults to two minutes.
    ready_timeout_ms: int | None = None
    #: Environment for the bake. Captured in the snapshot and therefore shared
    #: by every sandbox restored from it: configuration only, never a
    #: credential. Use ``rebind`` for those.
    envs: dict[str, str] = field(default_factory=dict)
    #: Values that must differ per sandbox.
    rebind: list[RebindVar] = field(default_factory=list)
    #: Command run in each restored sandbox once its rebind values are in
    #: place, before it is reported ready.
    after_restore_cmd: str | None = None
    #: Budget for ``after_restore_cmd``. Defaults to ten seconds.
    after_restore_timeout_ms: int | None = None
    #: Fail the create rather than serve it cold when nothing is baked. For
    #: tests and benchmarks that need to assert a warm start.
    require_warm: bool = False
    #: Ignore any existing snapshot and bake a fresh one.
    skip_cache: bool = False

    def __post_init__(self) -> None:
        """Reject the two recipes the backend would reject, at construction."""
        if not self.run_cmd and not self.start_cmd:
            raise ValueError("WarmRecipe needs at least one run_cmd or a start_cmd.")
        if self.after_start_cmd and not self.start_cmd:
            raise ValueError(
                "WarmRecipe.after_start_cmd needs a start_cmd: it runs once that process is up.",
            )

    def to_v1(self) -> V1SandboxWarmSpec:
        return V1SandboxWarmSpec(
            run_cmd=list(self.run_cmd),
            start_cmd=self.start_cmd,
            after_start_cmd=list(self.after_start_cmd),
            ready_cmd=self.ready_cmd.to_v1() if self.ready_cmd else None,
            ready_timeout_ms=self.ready_timeout_ms,
            envs=dict(self.envs),
            rebind=[v.to_v1() for v in self.rebind],
            after_restore_cmd=self.after_restore_cmd,
            after_restore_timeout_ms=self.after_restore_timeout_ms,
            require_warm=self.require_warm or None,
            skip_cache=self.skip_cache or None,
        )


WarmInput: TypeAlias = "WarmRecipe | V1SandboxWarmSpec | None"


def to_v1_warm(warm: WarmInput) -> V1SandboxWarmSpec | None:
    """Convert an SDK recipe (or pass through a ``V1SandboxWarmSpec``)."""
    if warm is None:
        return None
    if isinstance(warm, V1SandboxWarmSpec):
        return warm
    if isinstance(warm, WarmRecipe):
        return warm.to_v1()
    raise TypeError(f"warm must be a WarmRecipe or V1SandboxWarmSpec, got {type(warm)!r}")


@dataclass(frozen=True)
class WarmStatus:
    """Whether a sandbox restored from a baked snapshot, and if not, why.

    The failure mode of warm sandboxes is a cold start that looks exactly like a
    warm one, so check :attr:`state` rather than assuming.
    """

    state: WarmState = "unknown"
    #: Opaque digest of the recipe, image, shape and runtime version. Stable
    #: across sandboxes that share a snapshot; not a handle you pass back.
    template_key: str = ""
    #: Why the sandbox did not restore, when it did not.
    reason: str = ""
    #: Milliseconds spent restoring, when ``state`` is ``"restored"``.
    restore_ms: int = 0


def from_v1_warm_status(status: V1SandboxWarmStatus | None) -> WarmStatus | None:
    """Convert a backend status, mapping the wire enum to a short state.

    An unrecognised state becomes ``"unknown"`` rather than leaking a wire value
    like ``"SANDBOX_WARM_STATE_..."`` into comparisons that would silently never
    match.
    """
    if status is None:
        return None
    raw = getattr(status, "state", None)
    return WarmStatus(
        state=_WARM_STATES.get(str(raw), "unknown"),
        template_key=getattr(status, "template_key", None) or "",
        reason=getattr(status, "reason", None) or "",
        restore_ms=int(getattr(status, "restore_ms", None) or 0),
    )
