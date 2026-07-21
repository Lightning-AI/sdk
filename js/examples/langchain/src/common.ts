/**
 * Shared configuration and utilities for the coding agent.
 *
 * The LangGraph "brain" runs locally, so this module only holds the shared graph
 * state, terminal colors, and the configuration describing the *sandbox* in which
 * the agent's generated code is executed.
 */
import { Annotation } from "@langchain/langgraph";
import type { Code, ExecutionEvaluation } from "./nodes.js";

// --- LLM configuration -----------------------------------------------------
// The agent's "brain" is a standard LangChain `ChatOpenAI` model pointed at
// Lightning's OpenAI-compatible gateway (see src/llm.ts), authenticated with the
// same Lightning API key used for sandboxes -- so no separate LLM provider key
// is needed. Any model id from the gateway's catalog works here.
export const MODEL = "anthropic/claude-opus-4-8";
export const DEBUG_MODEL = "lightning-ai/deepseek-v4-pro";

// --- Sandbox configuration -------------------------------------------------
// The agent executes its generated code inside a Lightning sandbox. Lightning
// runtimes ship Python *or* Node, never the heavy ML stack, so we install the
// libraries the agent is expected to use (torch + transformers) at create time.
export const SANDBOX_RUNTIME = "python313";
export const SANDBOX_INSTANCE_TYPE = "cpu-4"; // 4 vCPU / 16 GB -- enough for CPU gpt2 inference
export const SANDBOX_STORAGE_GB = 20; // room for the torch wheel + cached HF models

// Installed into the sandbox before the agent runs any code. We pull the CPU
// build of torch from the PyTorch index (the default PyPI wheel bundles CUDA
// and is huge / pointless on a CPU sandbox).
export const SANDBOX_SETUP_SCRIPT =
  "set -eux; " +
  "pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu " +
  "'torch==2.5.0'; " +
  "pip install --no-cache-dir 'transformers==4.46.0'";

/**
 * The agent's graph state, one typed channel per field.
 *
 * Nodes return *partial* updates (only the channels they change) and LangGraph
 * merges them in — the idiomatic LangGraph.js pattern. Channels without a
 * `default` are `undefined` until a node sets them; `error` deliberately has no
 * default so `generate` can tell a first attempt (error unset) from a retry
 * (error present).
 */
export const GraphState = Annotation.Root({
  question: Annotation<string>,
  iterations: Annotation<number>({
    reducer: (_prev, next) => next,
    default: () => 0,
  }),
  generation: Annotation<Code | null>,
  error: Annotation<string>,
  output: Annotation<string>,
  evaluation: Annotation<ExecutionEvaluation | null>,
  response: Annotation<string>,
});

export type GraphStateType = typeof GraphState.State;
export type GraphUpdate = typeof GraphState.Update;

export const COLOR = {
  HEADER: "\u001b[95m",
  BLUE: "\u001b[94m",
  GREEN: "\u001b[92m",
  RED: "\u001b[91m",
  ENDC: "\u001b[0m",
} as const;
