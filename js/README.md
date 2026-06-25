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

## Documentation

For detailed documentation — PTY sessions, persistence & snapshots, filesystem operations, and the full API reference — see the [Lightning AI sandbox docs](https://lightning.ai/docs/platform/developers/sdk/sandbox).

## License

Apache-2.0
