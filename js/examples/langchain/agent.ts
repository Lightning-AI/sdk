/// <reference types="node" />
/**
 * Build a coding agent with Lightning Sandboxes and LangGraph.
 *
 * The agent is built with LangGraph: it generates Python code, then *executes
 * that code inside a Lightning sandbox* to check whether it actually runs, and
 * iterates on failures. Documentation crawled from the web informs its approach.
 *
 * How the pieces fit together:
 *   * The LangGraph "brain" runs locally on your machine; only the agent's
 *     generated code runs remotely, inside a Lightning sandbox.
 *   * The LLM is a standard LangChain `ChatOpenAI` model pointed at Lightning's
 *     OpenAI-compatible gateway (see `src/llm.ts`). The same Lightning API key
 *     authenticates both the sandbox API and the LLM, so a single `sk-lit-...`
 *     key is all you need -- no OpenAI/Anthropic key required.
 *   * The sandbox's ML dependencies (torch + transformers) are installed at
 *     create time (see `src/common.ts`).
 *   * A sandbox command's stdout and stderr arrive as one combined stream, so we
 *     redirect each to a separate file inside the sandbox and read them back to
 *     recover the (stdout, stderr) pair the graph nodes expect.
 *
 * Run it from this directory. Provide your Lightning API key via the environment
 * (recommended) or --api-key:
 *
 *   export LIGHTNING_SANDBOX_API_KEY=sk-lit-...
 *   npx tsx agent.ts --question "How do I run a pre-trained model from the transformers library?"
 */
import { randomUUID } from "node:crypto";
import { StateGraph, START, END } from "@langchain/langgraph";
import { Sandbox } from "@lightningai/sdk";
import { decideToCheckCodeExec, decideToFinish } from "./src/edges.js";
import { Nodes, type RunFn } from "./src/nodes.js";
import { retrieveDocs } from "./src/retrieval.js";
import {
  COLOR,
  GraphState,
  SANDBOX_INSTANCE_TYPE,
  SANDBOX_RUNTIME,
  SANDBOX_SETUP_SCRIPT,
  SANDBOX_STORAGE_GB,
} from "./src/common.js";

const MINUTES_MS = 60 * 1000;

// Environment variables checked (in order) when --api-key is not passed. The
// same Lightning key authenticates both the sandbox API and the LLM gateway.
const API_KEY_ENV_VARS = ["LIGHTNING_SANDBOX_API_KEY", "LIGHTNING_API_KEY"] as const;

// Where generated code and its captured streams live inside the sandbox.
const CODE_PATH = "/tmp/agent_code.py";
const OUT_PATH = "/tmp/agent_stdout.txt";
const ERR_PATH = "/tmp/agent_stderr.txt";

// The agent may download a model on first execution, so give each run room.
const EXEC_TIMEOUT_S = 600;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function resolveApiKey(cliValue: string | undefined): string {
  // Precedence: the explicit --api-key flag wins; otherwise we fall back to the
  // LIGHTNING_SANDBOX_API_KEY / LIGHTNING_API_KEY environment variables. We
  // never hard-code a key so the example is safe to share.
  if (cliValue) return cliValue;
  for (const envVar of API_KEY_ENV_VARS) {
    const value = process.env[envVar];
    if (value) return value;
  }
  console.error(
    "No Lightning API key found. Pass --api-key sk-lit-... or set one of: " +
      API_KEY_ENV_VARS.join(", "),
  );
  process.exit(1);
}

/**
 * Run a shell `script` in the sandbox and block until it exits; return its exit code.
 *
 * This is the robust way to run *long* commands. A plain synchronous
 * `runCommand` has a ~120s server-side deadline (the sandbox setup and some
 * code runs here take much longer), and while detached commands do run, the
 * backend's command-*status* endpoints don't reliably report completion or
 * output. So we launch the script detached, redirect its output to a file
 * (combined, or split into `stdoutPath`/`stderrPath` when both are given), and
 * have it write an exit-code sentinel file when it finishes -- then poll
 * `readFile` (which is reliable) until that sentinel appears.
 */
async function runAndWait(
  sb: Sandbox,
  script: string,
  {
    timeout,
    pollInterval = 2.0,
    stdoutPath,
    stderrPath,
  }: {
    timeout: number;
    pollInterval?: number;
    stdoutPath?: string;
    stderrPath?: string;
  },
): Promise<number> {
  const donePath = `/tmp/.done_${randomUUID().replace(/-/g, "")}`;
  let redirect: string;
  if (stdoutPath && stderrPath) {
    redirect = `>${stdoutPath} 2>${stderrPath}`;
  } else {
    redirect = stdoutPath ? `>${stdoutPath}` : ">/dev/null 2>&1";
  }
  // Run in a subshell so the redirect covers all of it, then record the exit
  // code the instant it finishes.
  const wrapped = `(\n${script}\n) ${redirect}\necho $? >${donePath}\n`;
  await sb.runCommand({ cmd: "sh", args: ["-c", wrapped], detached: true });

  const deadline = Date.now() + timeout * 1000;
  while (Date.now() < deadline) {
    const code = await sb.readFile({ path: donePath });
    if (code && code.trim()) {
      return parseInt(code.trim(), 10);
    }
    await sleep(pollInterval * 1000);
  }
  throw new Error(`command did not finish within ${timeout}s`);
}

/**
 * Create a Lightning sandbox with torch + transformers installed.
 *
 * Change this setup (and the retrieval logic in the retrieval module) if you
 * want the agent to give coding advice on other libraries!
 */
async function createSandbox(timeoutMs: number = 30 * MINUTES_MS): Promise<Sandbox> {
  console.log(
    `${COLOR.HEADER}🏖️  Creating sandbox` +
      ` (${SANDBOX_INSTANCE_TYPE}, runtime=${SANDBOX_RUNTIME})${COLOR.ENDC}`,
  );

  // Sandbox.create() is not auto-retried by the SDK and can hit transient 500s.
  let sb: Sandbox | undefined;
  let lastErr: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      sb = await Sandbox.create({
        name: "langchain",
        instanceType: SANDBOX_INSTANCE_TYPE,
        runtime: SANDBOX_RUNTIME,
        storageGb: SANDBOX_STORAGE_GB,
        timeout: timeoutMs,
      });
      break;
    } catch (err) {
      lastErr = err;
      if (attempt === 2) throw err;
      console.log(`${COLOR.RED}🏖️  create failed (${err}); retrying...${COLOR.ENDC}`);
      await sleep(2 ** attempt * 1000);
    }
  }
  if (!sb) throw new Error("unreachable", { cause: lastErr });

  console.log(
    `${COLOR.HEADER}🏖️  Installing torch + transformers in the sandbox` +
      ` (this can take a few minutes)${COLOR.ENDC}`,
  );
  const setupLog = "/tmp/setup.log";
  const exitCode = await runAndWait(sb, SANDBOX_SETUP_SCRIPT, {
    timeout: 900,
    pollInterval: 3.0,
    stdoutPath: setupLog,
  });
  if (exitCode !== 0) {
    const log = (await sb.readFile({ path: setupLog })) ?? "";
    await sb.delete();
    throw new Error(`sandbox dependency install failed (exit ${exitCode}):\n${log}`);
  }
  console.log(`${COLOR.GREEN}🏖️  Sandbox ready (${sb.sandboxId})${COLOR.ENDC}`);
  return sb;
}

/**
 * Execute `code` inside the sandbox, returning [exitCode, stdout, stderr].
 *
 * We reuse the same sandbox container for every run, preserving state.
 * Lightning merges stdout/stderr into one stream, so we redirect each to a file
 * in the sandbox and read them back to recover the separate streams the graph
 * nodes rely on.
 *
 * We return the process *exit code* alongside the streams: it -- not the mere
 * presence of stderr -- is what distinguishes a real failure from benign
 * warnings (e.g. Hugging Face writes model-download progress to stderr while
 * still exiting 0).
 */
const run: RunFn = async (code: string, sb: Sandbox): Promise<[number, string, string]> => {
  console.log(
    `${COLOR.HEADER}📦: Running in sandbox${COLOR.ENDC}\n` +
      `${COLOR.GREEN}${code}${COLOR.ENDC}`,
  );

  await sb.writeFile({ path: CODE_PATH, content: code });
  let returncode: number;
  try {
    returncode = await runAndWait(sb, `python -u ${CODE_PATH}`, {
      timeout: EXEC_TIMEOUT_S,
      pollInterval: 2.0,
      stdoutPath: OUT_PATH,
      stderrPath: ERR_PATH,
    });
  } catch {
    returncode = 1;
  }

  const stdout = (await sb.readFile({ path: OUT_PATH })) ?? "";
  const stderr = (await sb.readFile({ path: ERR_PATH })) ?? "";

  if (returncode !== 0) {
    console.log(`${COLOR.HEADER}📦: Failed with exitcode ${returncode}${COLOR.ENDC}`);
  }

  return [returncode, stdout, stderr];
};

async function constructGraph(
  sandbox: Sandbox,
  { debug = false, apiKey }: { debug?: boolean; apiKey?: string } = {},
) {
  // Crawl the transformers documentation to inform our code generation
  const context = await retrieveDocs(undefined, debug);

  const nodes = new Nodes(context, sandbox, run, { debug, apiKey });

  // Build the graph with the fluent, fully-typed StateGraph builder: nodes are
  // attached, then edges (static and conditional) wire up the control flow.
  return new StateGraph(GraphState)
    .addNode("generate", nodes.generate)
    .addNode("checkCodeImports", nodes.checkCodeImports)
    .addNode("checkCodeExecution", nodes.checkCodeExecution)
    .addNode("evaluateExecution", nodes.evaluateExecution)
    .addNode("finish", nodes.finish)
    .addEdge(START, "generate")
    .addEdge("generate", "checkCodeImports")
    .addConditionalEdges("checkCodeImports", decideToCheckCodeExec, {
      checkCodeExecution: "checkCodeExecution",
      generate: "generate",
    })
    .addEdge("checkCodeExecution", "evaluateExecution")
    .addConditionalEdges("evaluateExecution", decideToFinish, {
      finish: "finish",
      generate: "generate",
    })
    .addEdge("finish", END);
}

const DEFAULT_QUESTION =
  "How do I generate Python code using a pre-trained model from the transformers library?";

/** Compile the Python code generation agent graph and run it, returning the result. */
async function go(
  question: string = DEFAULT_QUESTION,
  { debug = false, apiKey }: { debug?: boolean; apiKey?: string } = {},
): Promise<string> {
  const sb = await createSandbox();

  try {
    const graph = await constructGraph(sb, { debug, apiKey });
    const runnable = graph.compile();
    const result = await runnable.invoke(
      { question, iterations: 0 },
      { recursionLimit: 50 },
    );
    return result.response;
  } finally {
    // finish() already deletes the sandbox on the happy path; this is a
    // best-effort safety net for every other path, so ignore "already deleted".
    try {
      await sb.delete();
    } catch {
      // Sandbox was likely already deleted by finish(); nothing to clean up.
    }
  }
}

interface Args {
  question: string;
  debug: boolean;
  apiKey?: string;
}

function parseArgs(argv: string[]): Args {
  const args: Args = { question: DEFAULT_QUESTION, debug: false };
  for (let i = 0; i < argv.length; i++) {
    const [flag, inlineValue] = argv[i].split(/=(.*)/s);
    const value = () => (inlineValue !== undefined ? inlineValue : argv[++i]);
    switch (flag) {
      case "--question":
        args.question = value();
        break;
      case "--debug":
        args.debug = true;
        break;
      case "--api-key":
        args.apiKey = value();
        break;
      default:
        throw new Error(`Unknown argument: ${flag}`);
    }
  }
  return args;
}

async function main(args: Args): Promise<void> {
  // The same Lightning key authenticates both the sandbox API and the LLM
  // gateway -- no separate LLM provider key required.
  const apiKey = resolveApiKey(args.apiKey);
  Sandbox.configure({ apiKey });

  let question = args.question;
  if (args.debug && question === DEFAULT_QUESTION) {
    question = "hi there, how are you?";
  }

  console.log(await go(question, { debug: args.debug, apiKey }));
}

main(parseArgs(process.argv.slice(2))).catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
