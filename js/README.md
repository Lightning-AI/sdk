<div align="center">

# @lightningai/sdk

**Create and control Lightning AI sandboxes from TypeScript.**

______________________________________________________________________

<p align="center">
  <a href="#quick-start">Quick start</a> •
  <a href="#examples">Examples</a> •
  <a href="#api-shape">API shape</a> •
  <a href="#development">Development</a> •
  <a href="https://lightning.ai/docs/platform/developers/sdk/sandbox">Docs</a>
</p>

[![npm](https://img.shields.io/npm/v/@lightningai/sdk.svg)](https://www.npmjs.com/package/@lightningai/sdk)
[![Node](https://img.shields.io/badge/node-%3E%3D22.0.0-brightgreen.svg)](package.json)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](../LICENSE)

</div>

# Why @lightningai/sdk?

`@lightningai/sdk` is the TypeScript SDK for Lightning AI sandboxes. Use it when
Node.js code needs an isolated machine for commands, file operations, PTY
sessions, snapshots, or short-lived automation.

The package is intentionally narrow: it focuses on sandboxes and mirrors the
Python sandbox surface where possible.

Build on [Lightning AI](https://lightning.ai), the platform for training,
deploying, and scaling AI applications with managed compute, collaborative
studios, and production endpoints.

# Quick start

Install the package:

```bash
npm install @lightningai/sdk
```

Set an API key:

```bash
export LIGHTNING_API_KEY="..."
```

Create a sandbox and run a command:

```ts
import { Sandbox } from "@lightningai/sdk";

const sandbox = await Sandbox.create({
  name: "typescript-readme",
  instanceType: "cpu-1",
});

const result = await sandbox.runCommand("echo", ["hello from Lightning"]);
console.log(result.output);

await sandbox.delete();
```

This package is ESM-only. In CommonJS projects, import it dynamically:

```js
const { Sandbox } = await import("@lightningai/sdk");
```

# Examples

## Files

```ts
import { Sandbox } from "@lightningai/sdk";

const sandbox = await Sandbox.create({ instanceType: "cpu-1" });

await sandbox.fs.writeFile({
  path: "/workspace/app.js",
  content: "console.log('hello from a file')\n",
});

const result = await sandbox.runCommand("node", ["/workspace/app.js"]);
console.log(result.output);

await sandbox.delete();
```

## Persistent sandbox

```ts
import { Sandbox } from "@lightningai/sdk";

const sandbox = await Sandbox.create({
  name: "persistent-devbox",
  instanceType: "cpu-1",
  persistent: true,
});

await sandbox.runCommand("mkdir", ["-p", "/workspace/project"]);
await sandbox.stop();

const resumed = await Sandbox.resume({ sandboxId: sandbox.sandboxId });
console.log(resumed.status);

await resumed.delete();
```

## PTY session

```ts
import { Sandbox, writeToStdout } from "@lightningai/sdk";

const sandbox = await Sandbox.create({ instanceType: "cpu-1" });

const pty = await sandbox.process.createPty({
  sessionName: "shell",
  onData: writeToStdout,
});

await pty.waitForConnection();
await pty.sendInput("python --version\n");

// A PTY is backed by a persistent `screen` session, so `exit` alone leaves the
// attach socket open and `pty.wait()` would block forever. Detach explicitly
// (or use `sandbox.process.killPtySession(...)` to also kill the screen session).
await pty.disconnect();
await pty.wait();

await sandbox.delete();
```

# API shape

| Area                          | Entry point                                                 |
| ----------------------------- | ----------------------------------------------------------- |
| Create/get/list/resume/delete | `Sandbox`                                                   |
| Run commands                  | `sandbox.runCommand(...)`                                   |
| Files and directories         | `sandbox.fs`                                                |
| PTY sessions                  | `sandbox.process`                                           |
| Snapshots                     | `sandbox.createSnapshot(...)`, `Sandbox.listSnapshots(...)` |
| Network egress policy         | `networkPolicy` on `Sandbox.create(...)`                    |

# Development

```bash
npm install
npm run build
npm test
```

The package is published as an ES module and requires Node.js 22 or newer.

# License

Apache-2.0. See [`../LICENSE`](../LICENSE).
