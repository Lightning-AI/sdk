"""Multi-tenant, Lambda-style execution with safe reuse via snapshots.

This is the pattern AI Factory asked about ("multi-tenant Lambda-style
functions"): one shared, warm function image + an isolated, ephemeral execution
per invocation.

  1. BUILD ONCE  — boot a sandbox, bake the function into it (deps + handler
     code), and snapshot it. The snapshot is an immutable "deployment package".
     You pay the cold dependency-install cost exactly once.

  2. INVOKE MANY — for each request (any tenant), restore a FRESH sandbox from
     that one snapshot, feed it the request event, run the handler, collect the
     result, then tear it down.

Why this is *safe* multi-tenant reuse:
  - The snapshot is a read-only base. Every restore gets its own overlay
    upperdir and its own gVisor sandbox, so invocations never share a mutable
    filesystem or process space — tenant A cannot observe tenant B's state (the
    handler asserts this below). You get Lambda's "clean environment per
    invocation" without re-installing dependencies each time; the per-invocation
    cost is just the ~200-300ms warm restore.

Lower-latency variant (not shown): keep a warm pool of persistent sandboxes
(`SandboxInstance.create(persistent=True)` + `.stop()` / `.resume()`) and reset
state between uses. Snapshot-fork (below) gives the strongest isolation;
pooling trades some isolation for lower latency.

Usage (from the ``python/`` directory):
  LIGHTNING_API_KEY=... LIGHTNING_CLOUD_URL=... PROJECT_ID=... \
    CLUSTER_ID=<cluster> CONCURRENCY=5 python examples/multi_tenant_lambda.py

Environment variables:
  LIGHTNING_API_KEY    Auth (or LIGHTNING_SANDBOX_API_KEY). Required.
  LIGHTNING_CLOUD_URL  Control-plane URL. Required for non-default endpoints.
  PROJECT_ID           Project the snapshot is uploaded under. Required.
  CLUSTER_ID           Cluster to place sandboxes on. Strongly recommended.
  LIGHTNING_ORG_ID     Organization scope, if your key spans multiple orgs.
  INSTANCE_TYPE        Sandbox machine shape (default: cpu-sandbox-2).
  RUNTIME              Sandbox base runtime (default: python313).
  CONCURRENCY          Number of concurrent invocations (default: 5).

Common issues / requirements:
  - 503 "no sandbox capacity available": usually NOT real capacity — it most
    often means the request landed on the wrong cluster. If you don't pass
    ``CLUSTER_ID`` the control plane uses its default cluster, whose nodes get
    filtered out (``wrong_cluster``) and the scheduler reports no eligible
    hosts. Set ``CLUSTER_ID`` to a cluster that actually has sandbox-capable
    nodes. (It can also be genuine capacity exhaustion on a small cluster, in
    which case retry shortly.)
  - Snapshots need a storage-backed cluster. ``snapshot()`` uploads the
    filesystem to object storage, so the sandbox cluster must resolve to a
    storage cluster. A compute-only cluster (e.g. bare-metal / machine) has no
    object store of its own and must have a parent *storage* cluster set;
    otherwise snapshot capture fails server-side with "parent cluster must be
    set". Today only Cloudflare R2-backed storage clusters implement snapshot
    upload credentials — other providers return "not implemented" — so the
    cluster's (parent) storage must be R2-backed for ``snapshot()`` to succeed.
    If you only need ephemeral sandboxes (no ``snapshot()`` / ``snapshot_id=``),
    this requirement does not apply.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from lightning_sdk.sandbox import RunCommandOpts, SandboxInstance

INSTANCE_TYPE = os.environ.get("INSTANCE_TYPE", "cpu-sandbox-2")
RUNTIME = os.environ.get("RUNTIME", "python313")
PROJECT_ID = os.environ.get("PROJECT_ID")
# Optional: pin placement to a specific cluster. Without it the control plane
# falls back to its default cluster, which may not host sandbox-capable nodes
# (you'll see a 503 "no sandbox capacity available" from a wrong-cluster filter).
CLUSTER_ID = os.environ.get("CLUSTER_ID")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "5"))

if not PROJECT_ID:
    print("PROJECT_ID env var is required (snapshot uploads are project-scoped).", file=sys.stderr)
    sys.exit(2)

# The function we "deploy". Reads an event JSON path from argv[1], does a bit of
# work that proves the baked-in dependency is present, and prints a JSON result
# to stdout. It also drops a marker into /tmp: a fresh restore must never see a
# previous invocation's marker — that's our isolation probe.
HANDLER_PY = r"""
import json, os, sys, time
import humanize  # pip-installed at build time; proves the snapshot baked deps in

event = json.load(open(sys.argv[1]))

marker = "/tmp/leaked-state.json"
previous = None
if os.path.exists(marker):
    with open(marker) as f:
        previous = json.load(f).get("tenant")
with open(marker, "w") as f:
    json.dump({"tenant": event["tenant"], "at": time.time()}, f)

print(json.dumps({
    "tenant": event["tenant"],
    "result": humanize.intcomma(event["n"] * 1000),
    "pid": os.getpid(),
    # Must be null for every invocation if isolation holds.
    "sawPreviousTenant": previous,
}))
"""


def build_golden_snapshot() -> str:
    """BUILD ONCE: bake deps + handler into a sandbox, snapshot it, throw it away."""
    builder = SandboxInstance.create(
        name="fn-builder", instance_type=INSTANCE_TYPE, runtime=RUNTIME, cluster_id=CLUSTER_ID
    )
    try:
        builder.mkdir("/opt/fn")
        builder.write_file("/opt/fn/handler.py", HANDLER_PY)
        install = builder.run_command(
            RunCommandOpts(cmd="python", args=["-m", "pip", "install", "--quiet", "humanize"])
        )
        if install.exit_code != 0:
            raise RuntimeError(f"pip install failed ({install.exit_code}): {install.output}")
        snap = builder.snapshot(project_id=PROJECT_ID)
        if snap.status != "ready":
            raise RuntimeError(f"snapshot not ready: {snap.status}")
        return snap.id
    finally:
        builder.delete()  # the builder only existed to bake the image


def invoke(snapshot_id: str, tenant: str, n: int) -> dict:
    """INVOKE: fork a fresh isolated sandbox from the snapshot, run, tear down."""
    t0 = time.monotonic()
    sb = SandboxInstance.create(
        name=f"fn-{tenant}",
        instance_type=INSTANCE_TYPE,
        runtime=RUNTIME,
        snapshot_id=snapshot_id,
        cluster_id=CLUSTER_ID,
    )
    warm_start_ms = round((time.monotonic() - t0) * 1000)
    try:
        sb.write_file("/tmp/event.json", json.dumps({"tenant": tenant, "n": n}))
        cmd = sb.run_command(
            RunCommandOpts(
                cmd="python",
                args=["/opt/fn/handler.py", "/tmp/event.json"],
                env={"TENANT": tenant},  # per-invocation injection (secrets/config go here)
            )
        )
        if cmd.exit_code != 0:
            raise RuntimeError(f"handler failed for {tenant} ({cmd.exit_code}): {cmd.output}")
        out = json.loads(cmd.output)
        out["warmStartMs"] = warm_start_ms
        return out
    finally:
        sb.delete()  # ephemeral, Lambda-style teardown


def main() -> None:
    # Credentials come from env (LIGHTNING_API_KEY / LIGHTNING_CLOUD_URL) at
    # import; configure explicitly if you prefer.
    if os.environ.get("LIGHTNING_ORG_ID"):
        SandboxInstance.configure(organization_id=os.environ["LIGHTNING_ORG_ID"])

    print(f"Building golden snapshot (instance={INSTANCE_TYPE}, runtime={RUNTIME})...")
    tb = time.monotonic()
    snapshot_id = build_golden_snapshot()
    print(f"Golden snapshot {snapshot_id} ready in {time.monotonic() - tb:.1f}s (cost paid once)")

    # Fan out N concurrent invocations across tenants, all forked from the one
    # immutable snapshot.
    tenants = [(f"tenant-{i}", i) for i in range(CONCURRENCY)]
    print(f"Invoking {len(tenants)} tenants concurrently from {snapshot_id}...")
    ti = time.monotonic()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(lambda t: invoke(snapshot_id, t[0], t[1]), tenants))
    print(f"All invocations completed in {time.monotonic() - ti:.1f}s wall")
    for r in results:
        print(f"  {r['tenant']:<10} result={r['result']:<10} pid={r['pid']} warm={r['warmStartMs']}ms")

    # Safe-reuse assertion: no invocation observed another tenant's marker.
    leaked = [r for r in results if r["sawPreviousTenant"] is not None]
    if leaked:
        raise SystemExit(f"ISOLATION VIOLATION — invocations saw prior tenant state: {leaked}")
    print(
        "OK: safe reuse verified — every invocation booted clean from the shared "
        "snapshot, with no cross-tenant filesystem/process state."
    )

    SandboxInstance.delete_snapshot(snapshot_id)
    print(f"Cleanup: deleted golden snapshot {snapshot_id}")


if __name__ == "__main__":
    main()
