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
  });
  console.log("Created sandbox:", sandbox.sandboxId);

  // --- Create an interactive PTY session -----------------------------------
  console.log("\n--- Interactive PTY ---");

  const pty = await sandbox.process.createPty({
    sessionName: "main-default",
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

  // Give the shell a moment to run the commands and stream their output back.
  await new Promise((r) => setTimeout(r, 2000));

  // A PTY is backed by a persistent `screen` session on the sandbox, so typing
  // `exit` only drops the *inner* shell -- the attach WebSocket stays open and
  // `pty.wait()` would block forever. Detach explicitly instead: `disconnect()`
  // closes the socket client-side, which is what makes `wait()` resolve. (To
  // also tear down the remote screen session, use `killPtySession()`, as the
  // background-session demo below does.)
  await pty.disconnect();

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
