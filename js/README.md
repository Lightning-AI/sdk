# @lightningai/sdk

TypeScript SDK for [Lightning AI](https://lightning.ai) sandboxes: create and manage sandboxes, run commands, and work with files inside a sandbox.

## Requirements

- **Node.js 22+**

## Install

```bash
npm install @lightningai/sdk
```

> **Note**
> This package is published as an ES Module (ESM) only. For applications using CommonJS, use `await import("@lightningai/sdk")` to import and use this package.

## Quick start

Set an API key (or pass `apiKey` to `Sandbox.configure()`):

```bash
export LIGHTNING_API_KEY=your_key
```

```ts
import { Sandbox } from "@lightningai/sdk";

async function main() {
  // Uses LIGHTNING_API_KEY from the environment by default
  // (optional: Sandbox.configure({ apiKey, organizationId, baseUrl }))

  const sandbox = await Sandbox.create({
    name: "quickstart",
    instanceType: "cpu-1",
  });

  const result = await sandbox.runCommand("echo", ["Hello, World!"]);
  console.log(result.output);

  await sandbox.delete();
}

main().catch(console.error);
```

Environment variables read by the SDK:

| Variable            | Purpose                                                   |
| ------------------- | --------------------------------------------------------- |
| `LIGHTNING_API_KEY` | API key if not passed via `configure()` / request options |

## PTY sessions

For interactive shells (REPLs, build watchers, anything that needs `stdin`/window-resize/ANSI), use the `sandbox.process` namespace instead of `runCommand`. PTY sessions are bridged over a WebSocket from the controlplane down to the in-sandbox SSH server, with the same xterm wire protocol the Lightning UI's web terminal uses.

PTY support requires Node 22+ (for the built-in `WebSocket` global).

### Create a session

```ts
const pty = await sandbox.process.createPty({
  sessionName: "build",
  clusterId: sandbox.clusterId,
  cwd: "/app",
  cols: 120,
  rows: 30,
  envs: { TERM: "xterm-256color" },
  onData: (chunk) => process.stdout.write(chunk),
});

await pty.waitForConnection();
await pty.sendInput("npm test\n");
await pty.sendInput("exit\n");

const result = await pty.wait();
console.log(`exit code: ${result.exitCode}`);
```

| Option        | Type                        | Description                                                            |
| ------------- | --------------------------- | ---------------------------------------------------------------------- |
| `sessionName` | `string`                    | Session identifier (used by `connectPty`)                              |
| `clusterId`   | `string`                    | Cluster the sandbox runs on (`sandbox.clusterId`)                      |
| `cwd`         | `string`                    | Initial working directory                                              |
| `envs`        | `Record<string, string>`    | Environment variables exported into the session                        |
| `cols`        | `number`                    | Initial terminal columns (default 80)                                  |
| `rows`        | `number`                    | Initial terminal rows (default 24)                                     |
| `onData`      | `(chunk: Uint8Array)=>void` | Callback for every chunk of shell output (defaults to `writeToStdout`) |

If `onData` is omitted, the SDK uses the exported `writeToStdout` helper, which forwards raw shell bytes to `process.stdout`. Pass `onData: () => {}` to suppress.

### Reconnect to a session

```ts
const pty = await sandbox.process.connectPty("build", sandbox.clusterId, {
  onData: (chunk) => process.stdout.write(chunk),
});
```

### List, inspect, and kill sessions

```ts
const sessions = await sandbox.process.listPtySessions();
for (const s of sessions) {
  console.log(s.id, s.active, s.cols, s.rows);
}

const info = await sandbox.process.getPtySessionInfo("build");
await sandbox.process.killPtySession("build");
```

### Resize

Resize from a handle (preferred — works without a server round-trip):

```ts
await pty.resize(150, 40);
```

Or via the namespace, which finds the live handle in this process:

```ts
await sandbox.process.resizePtySession("build", 150, 40);
```

### `PtyHandle` reference

| Member                            | Description                                              |
| --------------------------------- | -------------------------------------------------------- |
| `sendInput(string \| Uint8Array)` | Send raw bytes to the shell (e.g. `"\u0003"` for Ctrl+C) |
| `resize(cols, rows)`              | Send a resize control frame                              |
| `wait()`                          | Resolve when the WebSocket closes; returns `PtyResult`   |
| `waitForConnection(timeoutMs?)`   | Resolve when the WebSocket opens                         |
| `kill()`                          | Send Ctrl+C and disconnect                               |
| `disconnect()`                    | Close the WebSocket without killing the shell            |
| `isConnected()`                   | Whether the WebSocket is OPEN                            |
| `exitCode`                        | `0` on clean close, `-1` on abnormal, `null` while alive |
| `error`                           | Termination reason on abnormal close, otherwise `null`   |
| `size`                            | Most recent `{ cols, rows }`                             |

> **Note on cross-process persistence.** Within a single SDK process, every PTY method works against an in-process registry. Reattaching from a *different* process to a session that's still running on the sandbox requires the runtime image to ship `screen` (or similar) and the in-sandbox SSH login shell to honor `LAI_TERM_SESSION_NAME` / `LAI_TERM_RESTORE` — both of which are tracked as a follow-up to this initial parity work. The API surface above does not change either way.

## Persistence & snapshots

Sandboxes can persist their filesystem across stops and idle eviction. Create a sandbox with `persistent: true` and its **id becomes a durable handle** — the controlplane auto-snapshots on idle/stop and transparently restores it the next time the id is accessed.

```ts
const sandbox = await Sandbox.create({
  name: "durable-job",
  instanceType: "cpu-1",
  persistent: true,
  projectId: "proj-123", // recommended for persistent sandboxes
});

// ... do work, write files ...

// Pause: captures an auto-snapshot keyed to the sandbox id and stops the server.
const { autoSnapshotId } = await sandbox.stop();

// Later — resume by id, preserving filesystem state. Blocks until running.
const resumed = await Sandbox.resume({ sandboxId: sandbox.sandboxId });
// (or `await sandbox.resume()`)
```

`Sandbox.get` / `Sandbox.list` surface a paused persistent sandbox with `status: "paused"`.

### Named snapshots

Capture an explicit, named snapshot you can boot new sandboxes from:

```ts
const snap = await sandbox.createSnapshot({ excludes: ["node_modules"] });
// snap.status starts as "saving"; poll until "ready":
const ready = await Sandbox.getSnapshot(snap.id);

// Boot a fresh sandbox from the snapshot:
const clone = await Sandbox.create({
  name: "from-snapshot",
  instanceType: "cpu-1",
  snapshotId: snap.id,
});

const { snapshots } = await Sandbox.listSnapshots({ projectId: "proj-123" });
await Sandbox.deleteSnapshot(snap.id);
```

## License

Apache-2.0
