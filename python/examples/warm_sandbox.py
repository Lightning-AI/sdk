"""Warm sandboxes: hand back a notebook whose kernel is already running.

A warm recipe says what the sandbox should have done before you get it.
Lightning runs it once, snapshots the result, and restores later sandboxes with
the same recipe from that snapshot. The recipe is the cache key, so there is no
template id to keep in sync — rebuild the image and the next create bakes
afresh on its own.

Run it three times to see the whole lifecycle:

    python examples/warm_sandbox.py     # cold: the recipe runs inline
    python examples/warm_sandbox.py     # cold, and a bake starts behind you
    python examples/warm_sandbox.py     # restored, in a fraction of the time

Needs a teamspace-scoped API key:

    export LIGHTNING_SANDBOX_API_KEY=...
"""

from __future__ import annotations

import time

from lightning_sdk.sandbox import RebindVar, Sandbox, WarmRecipe, wait_for_port

# Jupyter cannot rotate --IdentityProvider.token in place, and a token passed at
# startup is baked into the shared snapshot — every restored sandbox would keep
# accepting it. This provider reads the per-sandbox token on each request
# instead, so the value Lightning rebinds at restore takes effect immediately.
IDENTITY_PROVIDER = """
mkdir -p /opt/warm && cat > /opt/warm/warm_identity.py <<'PY'
from pathlib import Path
from jupyter_server.auth.identity import PasswordIdentityProvider


class WarmIdentityProvider(PasswordIdentityProvider):
    @property
    def token(self):
        return Path("/run/lightning/warm/JUPYTER_TOKEN").read_text().strip()
PY
"""

recipe = WarmRecipe(
    run_cmd=[
        "pip install jupyterlab numpy pandas",
        # Pay the import cost once, at bake time, instead of on every create.
        "python -c 'import numpy, pandas'",
        IDENTITY_PROVIDER,
    ],
    start_cmd=(
        "PYTHONPATH=/opt/warm jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root "
        "--ServerApp.identity_provider_class=warm_identity.WarmIdentityProvider"
    ),
    # A port check, not a URL check: /api/status answers 403 until you
    # authenticate, so "is it listening" is the honest signal here.
    ready_cmd=wait_for_port(8888),
    rebind=[
        RebindVar(
            name="JUPYTER_TOKEN",
            source="generated-token",
            # The bake runs against this, so the shared snapshot never carries a
            # live credential.
            bake_value="bake-placeholder",
        )
    ],
)

started = time.monotonic()
sandbox = Sandbox.create(
    name=f"warm-notebook-{int(time.time())}",
    instance_type="cpu-2",
    image="docker.io/library/python:3.13",
    ports=[8888],
    warm=recipe,
)
elapsed = time.monotonic() - started

# A cold start looks exactly like a warm one from the outside, so check.
status = sandbox.warm
print(f"state:   {status.state if status else 'no recipe'}")
if status and status.state != "restored":
    print(f"reason:  {status.reason}")
print(f"created in {elapsed:.1f}s")

# Returned once, on create — keep it if you need it.
token = sandbox.warm_secrets.get("JUPYTER_TOKEN", "")
print(f"token:   {token[:8]}…" if token else "token:   (none)")

# The token the sandbox serves with is the one you were handed, and the bake's
# placeholder is not accepted.
mine = sandbox.run_command(f'curl -s -o /dev/null -w "%{{http_code}}" -H "Authorization: token {token}" http://localhost:8888/api/status')
placeholder = sandbox.run_command(
    'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token bake-placeholder" http://localhost:8888/api/status'
)
print(f"my token → {mine.output.strip()}, bake placeholder → {placeholder.output.strip()}")

sandbox.delete()
