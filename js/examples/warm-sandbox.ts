/**
 * Warm sandboxes: hand back a notebook whose kernel is already running.
 *
 * A warm recipe says what the sandbox should have done before you get it.
 * Lightning runs it once, snapshots the result, and restores later sandboxes
 * with the same recipe from that snapshot. The recipe is the cache key, so
 * there is no template id to keep in sync — rebuild the image and the next
 * create bakes afresh on its own.
 *
 * Run it three times to see the whole lifecycle:
 *
 *   npx tsx examples/warm-sandbox.ts   # cold: the recipe runs inline
 *   npx tsx examples/warm-sandbox.ts   # cold, and a bake starts behind you
 *   npx tsx examples/warm-sandbox.ts   # restored, in a fraction of the time
 *
 * Needs a teamspace-scoped API key:
 *
 *   export LIGHTNING_SANDBOX_API_KEY=...
 */
import { Sandbox, waitForPort, type WarmRecipe } from "../src/index.js";

// Jupyter cannot rotate --IdentityProvider.token in place, and a token passed
// at startup is baked into the shared snapshot — every restored sandbox would
// keep accepting it. This provider reads the per-sandbox token on each request
// instead, so the value Lightning rebinds at restore takes effect immediately.
const identityProvider = [
  "mkdir -p /opt/warm && cat > /opt/warm/warm_identity.py <<'PY'",
  "from pathlib import Path",
  "from jupyter_server.auth.identity import PasswordIdentityProvider",
  "",
  "",
  "class WarmIdentityProvider(PasswordIdentityProvider):",
  "    @property",
  "    def token(self):",
  '        return Path("/run/lightning/warm/JUPYTER_TOKEN").read_text().strip()',
  "PY",
].join("\n");

const recipe: WarmRecipe = {
  runCmd: [
    "pip install jupyterlab numpy pandas",
    // Pay the import cost once, at bake time, instead of on every create.
    "python -c 'import numpy, pandas'",
    identityProvider,
  ],
  startCmd:
    "PYTHONPATH=/opt/warm jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root " +
    "--ServerApp.identity_provider_class=warm_identity.WarmIdentityProvider",
  // A port check, not a URL check: /api/status answers 403 until you
  // authenticate, so "is it listening" is the honest signal here.
  readyCmd: waitForPort(8888),
  rebind: [
    {
      name: "JUPYTER_TOKEN",
      source: "generated-token",
      // The bake runs against this, so the shared snapshot never carries a
      // live credential.
      bakeValue: "bake-placeholder",
    },
  ],
};

const started = Date.now();
const sandbox = await Sandbox.create({
  name: `warm-notebook-${Date.now()}`,
  instanceType: "cpu-2",
  image: "docker.io/library/python:3.13",
  ports: [8888],
  warm: recipe,
});
const elapsed = ((Date.now() - started) / 1000).toFixed(1);

// A cold start looks exactly like a warm one from the outside, so check.
console.log(`state:   ${sandbox.warm?.state ?? "no recipe"}`);
if (sandbox.warm && sandbox.warm.state !== "restored") {
  console.log(`reason:  ${sandbox.warm.reason ?? ""}`);
}
console.log(`created in ${elapsed}s`);

// Returned once, on create — keep it if you need it.
const token = sandbox.warmSecrets.JUPYTER_TOKEN ?? "";
console.log(token ? `token:   ${token.slice(0, 8)}…` : "token:   (none)");

// The token the sandbox serves with is the one you were handed, and the bake's
// placeholder is not accepted.
const status = (authToken: string) =>
  sandbox.runCommand("sh", [
    "-lc",
    `curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token ${authToken}" http://localhost:8888/api/status`,
  ]);

const mine = await status(token);
const placeholder = await status("bake-placeholder");
console.log(`my token → ${mine.output.trim()}, bake placeholder → ${placeholder.output.trim()}`);

await sandbox.delete();
