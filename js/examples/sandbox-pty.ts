/// <reference types="node" />
/**
 * Demonstrates the PTY (pseudo-terminal) namespace on a sandbox:
 * creating an interactive session, streaming output, sending input,
 * resizing, and tearing it down.
 *
 * Requires Node 22+ for the built-in WebSocket global.
 *
 * Usage:
 *   LIGHTNING_API_KEY=... npx tsx examples/sandbox-pty.ts
 */
import { Sandbox } from "../src/index.js";

async function main() {
  const sandbox = await Sandbox.create({
    name: "pty-example",
    instanceType: "cpu-2",
    clusterId: "baremetal",
  });
  console.log("Created sandbox:", sandbox.sandboxId);

  // --- Create an interactive PTY session -----------------------------------
  console.log("\n--- Interactive PTY ---");

  const pty = await sandbox.process.createPty({
    sessionName: "main-default",
    clusterId: sandbox.clusterId,
    cwd: "/root",
    cols: 120,
    rows: 30,
    envs: { TERM: "xterm-256color" },
    // `onData` is omitted: the SDK defaults to `writeToStdout`, which forwards
    // raw shell bytes to `process.stdout` (mirrors Python's default).
  });

  await pty.waitForConnection();

  await pty.sendInput("uname -a\n");
  await pty.sendInput("ls -la /\n");

  // Pretend the user just resized their terminal window.
  await pty.resize(150, 40);

  // Cleanly exit the shell so .wait() returns.
  await pty.sendInput("exit\n");

  const result = await pty.wait();
  console.log(`\nPTY closed: exitCode=${result.exitCode} error=${result.error}`);

  // --- Listing / inspecting / killing sessions -----------------------------
  console.log("\n--- Session bookkeeping ---");

  const sessions = await sandbox.process.listPtySessions();
  console.log(`Active sessions: ${sessions.length}`);
  for (const s of sessions) {
    console.log(`  ${s.id} active=${s.active} ${s.cols}x${s.rows ?? "?"}`);
  }

  // Spawn a background loop and demonstrate killPtySession.
  const bg = await sandbox.process.createPty({
    sessionName: "main-background",
    clusterId: sandbox.clusterId,
    onData: () => { },
  });
  await bg.waitForConnection();
  await bg.sendInput("while true; do echo tick; sleep 1; done\n");
  await new Promise((r) => setTimeout(r, 2000));
  await sandbox.process.killPtySession("main-background");
  console.log("Killed background session");

  await sandbox.delete();
  console.log("\nSandbox deleted");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
