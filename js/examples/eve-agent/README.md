# Eve agent on Lightning AI

A compact, production-shaped [Eve](https://eve.dev/) agent with both halves of
the runtime on Lightning AI:

- Claude Opus 4.8 is called through the Anthropic-compatible
  `https://lightning.ai/v1/messages` API.
- Eve's shell and file tools run in a persistent Lightning CPU sandbox through
  a custom `SandboxBackend` adapter.

The adapter maps Eve's `/workspace`, command/process, file, and lifecycle APIs
onto the Lightning JavaScript SDK. Each Eve session receives its own sandbox;
stopping the server snapshots it, and the next run resumes it by sandbox ID.

## Run it

Node 24+ and `LIGHTNING_API_KEY` are required. From this directory:

```bash
npm install
npm run dev
```

The scripts automatically load the repository-root `.env` when it exists.
Otherwise, export `LIGHTNING_API_KEY` before running them.

Try prompts that force real sandbox work:

```text
Create a small TypeScript CLI in /workspace/hello, run it, and show me the result.
Inspect the sandbox, then write /workspace/notes.md with a short system report.
Read /workspace/notes.md from our previous turn and add the current kernel version.
```

The default Eve HTTP channel is also available at `http://127.0.0.1:2000/eve/v1`.
For a headless server, use `npm run dev:no-ui`.

## Using Lightning models API

Eve accepts baseURL and authToken options to connect to the Lightning models API and since we support Anthropic models, this works out of the box:

```js
const lightning = createAnthropic({
  baseURL: "https://lightning.ai/v1",
  authToken: apiKey,
});

export default defineAgent({
  model: lightning("claude-opus-4-8"),
  reasoning: "high",
  limits: {
    maxOutputTokensPerSession: 40_000,
  },
});
```

## Using Lightning sandboxes

Eve allows you to define custom sandbox backends, to add lightning:

```js
export default defineSandbox({
  description: "A durable Lightning AI CPU sandbox with a persistent /workspace.",
  backend: lightningSandbox({
    instanceType: "cpu-1",
    networkPolicy: "allow-all",
    timeout: 30 * 60_000,
  }),
});
```

## Files worth reading

- `agent/agent.ts` configures Lightning's Anthropic-compatible Models API.
- `agent/sandbox.ts` selects the Lightning backend and compute policy.
- `lib/lightning-sandbox.ts` implements Eve's public sandbox backend contract.
- `agent/tools/sandbox_status.ts` shows how authored tools access the same live
  sandbox with `ctx.getSandbox()`.

The endpoint currently expects Anthropic's native `claude-opus-4-8` model ID in
the request body. The provider namespace belongs in gateway-style IDs, but
`anthropic/claude-opus-4-8` is rejected by `lightning.ai/v1/messages`.
