# Code agent with Lightning Sandboxes and LangChain

This example builds a **coding agent** that writes Python code and then *actually
runs it* to check whether it works — iterating on failures until it succeeds.

The agent is orchestrated with
[LangGraph](https://github.com/langchain-ai/langgraphjs), the LLM is driven with
the standard LangChain [`ChatOpenAI`](https://js.langchain.com/docs/integrations/chat/openai/)
integration, and — the key part — the agent's generated code executes inside an
isolated [Lightning Sandbox](https://lightning.ai) so it can't touch your
machine, even under prompt injection.

## Why a sandbox?

An LLM that writes code is only useful if you can *run* that code — but running
model-generated code on your own machine is dangerous. The sandbox gives the
agent a real, disposable Python environment to execute in: the LangGraph "brain"
runs locally, and only the untrusted generated code runs remotely.

## How it works

The agent is a `StateGraph` built with the fluent, fully-typed LangGraph.js
builder in `agent.ts`; the nodes live in `src/nodes.ts` and the conditional-edge
routers in `src/edges.ts`. Every node returns a *partial* state update and
LangGraph merges it into the typed channels declared in `src/common.ts`:

```
generate ──▶ checkCodeImports ──▶ checkCodeExecution ──▶ evaluateExecution ──▶ finish
    ▲               │                                            │
    └───────────────┴────────────────── retry ───────────────────┘
```

1. **`generate`** — a LangChain LCEL chain
   (`PromptTemplate | chatModel.withStructuredOutput(Code)`) asks the model for
   a structured `{prefix, imports, code}` solution, using crawled documentation
   as context.
1. **`checkCodeImports`** — runs *just the imports* in the sandbox. A non-zero
   exit code means the imports are broken → regenerate with the error as
   feedback.
1. **`checkCodeExecution`** — runs the full code block in the sandbox and
   captures its stdout/stderr and exit code.
1. **`evaluateExecution`** — the model judges whether the run succeeded and
   decides `finish` or `retry`.
1. **`finish`** — assembles the final answer (approach + code + real execution
   output) and deletes the sandbox.

Because Lightning merges a command's stdout and stderr into one stream, `run()`
in `agent.ts` redirects each to a separate file in the sandbox and reads them
back, and it returns the process **exit code** — that, not the mere presence of
stderr, is what distinguishes a real failure from benign warnings (e.g. Hugging
Face writes model-download progress to stderr while still exiting 0).

## One key, no extra LLM provider account

Lightning exposes an OpenAI-compatible LLM gateway at
`{LIGHTNING_CLOUD_URL}/api/v1`, authenticated with the *same* `sk-lit-...` key
used for sandboxes. `src/llm.ts` simply points `ChatOpenAI` at it via
`baseURL`, so `bindTools` / `withStructuredOutput` / LCEL all work exactly as
they would against OpenAI — with no separate OpenAI or Anthropic key.

Pick any model from your gateway's catalog in `src/common.ts`:

```ts
export const MODEL = "anthropic/claude-opus-4-8";
export const DEBUG_MODEL = "lightning-ai/deepseek-v4-pro";
```

## Repo structure

| File               | Purpose                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------- |
| `agent.ts`         | Entry point: creates the sandbox, builds + runs the graph, defines `run()`.                 |
| `src/common.ts`    | Shared config: model ids, sandbox runtime/instance, dependency install script, graph state. |
| `src/llm.ts`       | Builds a `ChatOpenAI` wired to Lightning's gateway.                                         |
| `src/nodes.ts`     | Graph nodes (the actions that mutate state).                                                |
| `src/edges.ts`     | Graph edges (the transitions between nodes).                                                |
| `src/retrieval.ts` | Crawls the docs used as context for generation.                                             |

## Running it

Install the "brain" dependencies (torch + transformers are installed *in the
sandbox* at create time, not here):

```bash
npm install
```

Provide your Lightning API key (and cloud URL if you're not on the default):

```bash
export LIGHTNING_API_KEY=sk-lit-...
# export LIGHTNING_CLOUD_URL=https://lightning.ai   # the default
```

Then run from this directory:

```bash
npx tsx agent.ts --question "How do I run a pre-trained model from the transformers library?"
```

Useful flags:

- `--debug` — shorter doc context and a smaller/faster model (`DEBUG_MODEL`).
- `--api-key sk-lit-...` — pass the key explicitly instead of via the environment.

### Expected output

```
---GENERATE SOLUTION---
---CHECKING CODE IMPORTS---
---CODE IMPORT CHECK: SUCCESS---
---CHECKING CODE EXECUTION---
---CODE BLOCK CHECK: SUCCESS---
---EVALUATING EXECUTION---
---DECISION: FINISH---
---FINISHING---
To generate Python code using a pre-trained model from the transformers library, ...

from transformers import pipeline
...

Result of code execution:
# Python function to compute the factorial of a number
def factorial(n):
    ...
```

## Adapting it

To make the agent an expert on a *different* library, change two things:

1. The sandbox dependency install (`SANDBOX_SETUP_SCRIPT` in `src/common.ts`).
1. The documentation URL crawled in `src/retrieval.ts`.

```
```
