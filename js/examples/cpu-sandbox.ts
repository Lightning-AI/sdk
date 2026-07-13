/**
 * Create a CPU sandbox, run a command, and tear it down.
 *
 * Usage:
 *   LIGHTNING_SANDBOX_API_KEY=... npx tsx examples/cpu-sandbox.ts
 */
import { Sandbox } from "../src/index.js";

async function main() {
  const t0 = performance.now();
  const sandbox = await Sandbox.create({
    name: "cpu-example",
    instanceType: "cpu-1",
  });
  const tCreate = performance.now();
  console.log("Created sandbox:", sandbox.sandboxId, `(${((tCreate - t0) / 1000).toFixed(1)}s)`);

  const result = await sandbox.runCommand("uname", ["-a"]);
  const tCmd = performance.now();
  console.log("Exit code:", result.exitCode);
  console.log("Output:", result.output);
  console.log(`Command took ${((tCmd - tCreate) / 1000).toFixed(1)}s`);

  await sandbox.delete();
  const tDelete = performance.now();
  console.log(`Sandbox deleted (${((tDelete - tCmd) / 1000).toFixed(1)}s)`);
  console.log(`Total: ${((tDelete - t0) / 1000).toFixed(1)}s`);
}

main().catch(console.error);
