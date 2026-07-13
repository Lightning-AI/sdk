/// <reference types="node" />
/**
 * Build a stateful, sandboxed code interpreter on a Lightning Sandbox.
 *
 * It runs a long-lived Python "driver program" inside the sandbox that:
 *
 *   * listens for code sent on its standard input (`stdin`),
 *   * `exec`s that code against a *persistent* `globals` dict (so the
 *     interpreter is stateful across calls), and
 *   * returns the captured `stdout` / `stderr` as JSON on its standard
 *     output (`stdout`).
 *
 * Because we're inside a sandbox, using the "unsafe" `exec()` is fine.
 *
 * To talk to that long-lived program we need a live, bidirectional connection.
 * `sandbox.runCommand` is request/response with no persistent stdin, so we use
 * a **PTY session** (`sandbox.process.createPty`) instead. A PTY echoes input
 * and merges stdout/stderr into one stream, so the driver wraps every reply in
 * unique sentinel markers that we parse out of the terminal byte stream.
 *
 * One more PTY quirk we work around: the interactive-input transport silently
 * drops lines containing double quotes (`"`), so we cannot feed raw JSON in on
 * `stdin`. Instead we base64-encode the code (URL-safe alphabet, no quotes) on
 * the way in; the driver decodes it. The reply on the way out is plain JSON,
 * which is unaffected.
 *
 * Usage:
 *   # Provide your Lightning API key via the environment (recommended):
 *   export LIGHTNING_SANDBOX_API_KEY=sk-lit-...
 *   npx tsx interpreter-sandbox.ts
 *
 *   # ...or pass it (and any other setting) explicitly:
 *   npx tsx interpreter-sandbox.ts --api-key sk-lit-... --instance-type cpu-2
 */
import { Sandbox } from "../src/index.js";
import type { PtyHandle } from "../src/index.js";

// Environment variables checked (in order) when --api-key is not passed.
const API_KEY_ENV_VARS = ["LIGHTNING_SANDBOX_API_KEY", "LIGHTNING_API_KEY"] as const;

// Sentinel markers the driver wraps each JSON reply in. A PTY echoes our input
// and mixes stdout+stderr into one stream, so we can't assume "one JSON object
// per line". Instead the driver brackets each reply with these unlikely tokens
// and we slice them out of the accumulated terminal output.
//
// Use *printable* tokens, not ASCII control bytes: writing e.g. \x05 (ENQ) to a
// terminal triggers "answerback" and quietly breaks the line discipline, so the
// driver would stop receiving our stdin entirely.
const RESULT_START = "<<<<<INTERP_RESULT_8f3a2b1c>>>>>";
const RESULT_END = "<<<<<INTERP_END_8f3a2b1c>>>>>";
// Printed once on stderr when the driver is up and listening for commands.
const READY_MARKER = "<<<<<INTERP_READY_8f3a2b1c>>>>>";

// The Python "driver program" shipped into the sandbox. It's the exact same
// long-lived REPL the Python example runs; we boot it with `python3 -u`.
const DRIVER_PROGRAM = `def driver_program():
    import base64
    import json
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    # Sentinels must match the client side (kept inline so this function is
    # self-contained when shipped into the sandbox).
    RESULT_START = "<<<<<INTERP_RESULT_8f3a2b1c>>>>>"
    RESULT_END = "<<<<<INTERP_END_8f3a2b1c>>>>>"
    READY_MARKER = "<<<<<INTERP_READY_8f3a2b1c>>>>>"

    # When you \`exec\` code in Python, you can pass in a dictionary that defines
    # the global variables the code has access to. We reuse one dict for the
    # whole session, which is what makes the interpreter stateful.
    session_globals: dict = {}

    sys.stderr.write(READY_MARKER + "\\n")
    sys.stderr.flush()

    while True:
        line = sys.stdin.readline()
        if not line:  # stdin closed -> shut the driver down
            break
        line = line.strip()
        if not line:
            continue

        # Each command line is URL-safe base64 of the code to run (raw JSON on
        # stdin is unreliable through the PTY, which drops double quotes).
        try:
            code = base64.urlsafe_b64decode(line.encode()).decode()
        except Exception:
            continue  # ignore terminal echo / malformed noise

        # Capture the executed code's outputs.
        stdout_io, stderr_io = StringIO(), StringIO()
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            try:
                exec(code, session_globals)
            except Exception as e:
                print(f"Execution Error: {e}", file=sys.stderr)
        result = {
            "stdout": stdout_io.getvalue(),
            "stderr": stderr_io.getvalue(),
        }

        sys.stdout.write(RESULT_START + json.dumps(result) + RESULT_END)
        sys.stdout.flush()
`;

interface InterpreterResult {
  stdout?: string;
  stderr?: string;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** A stateful code interpreter backed by a Lightning Sandbox PTY session. */
class SandboxInterpreter {
  private readonly sandbox: Sandbox;
  private readonly chunks: Uint8Array[] = [];
  private consumed = 0; // how many complete result blocks we've returned
  private pty: PtyHandle | null = null;

  constructor(sandbox: Sandbox) {
    this.sandbox = sandbox;
  }

  private text(): string {
    return Buffer.concat(this.chunks.map((c) => Buffer.from(c))).toString("utf-8");
  }

  async start(): Promise<void> {
    // Ship the driver into the sandbox. Running the file boots the interpreter
    // loop (we append a call to `driver_program()`).
    const driverCommand = `${DRIVER_PROGRAM}\n\ndriver_program()\n`;
    await this.sandbox.writeFile({ path: "/root/driver.py", content: driverCommand });

    // Open a live PTY and accumulate everything it emits into a buffer.
    this.pty = await this.sandbox.process.createPty({
      sessionName: "interpreter",
      cwd: "/root",
      cols: 200,
      rows: 50,
      onData: (chunk) => this.chunks.push(chunk),
    });
    await this.pty.waitForConnection(30_000);

    // `-u` keeps stdout/stderr unbuffered so replies arrive live. The driver
    // turns the interactive shell into a clean JSON request/response pipe.
    await this.pty.sendInput("python3 -u /root/driver.py\n");
    await this.waitFor(READY_MARKER, 30_000);
  }

  private async waitFor(marker: string, timeoutMs: number): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (this.text().includes(marker)) return;
      await sleep(100);
    }
    throw new Error("Timed out waiting for driver (looking for marker).");
  }

  /** Block until the next complete result block is available, then parse it. */
  private async nextResult(timeoutMs: number): Promise<InterpreterResult> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const text = this.text();
      const blocks: string[] = [];
      let searchFrom = 0;
      while (true) {
        const start = text.indexOf(RESULT_START, searchFrom);
        if (start === -1) break;
        const end = text.indexOf(RESULT_END, start);
        if (end === -1) break; // reply still streaming in
        blocks.push(text.slice(start + RESULT_START.length, end));
        searchFrom = end + RESULT_END.length;
      }

      if (blocks.length > this.consumed) {
        const payload = blocks[this.consumed];
        this.consumed += 1;
        return JSON.parse(payload) as InterpreterResult;
      }
      await sleep(50);
    }
    throw new Error("Timed out waiting for code execution result.");
  }

  /** Send a snippet to the interpreter, print its output, return the result. */
  async runCode(code: string, timeoutMs = 30_000): Promise<InterpreterResult> {
    // Node's base64url omits `=` padding, but Python's urlsafe_b64decode
    // requires it -- re-pad so the driver can decode the line.
    let payload = Buffer.from(code, "utf-8").toString("base64url");
    const pad = payload.length % 4;
    if (pad) payload += "=".repeat(4 - pad);
    await this.pty!.sendInput(payload + "\n");
    const result = await this.nextResult(timeoutMs);

    process.stdout.write(result.stdout ?? "");
    if (result.stderr) {
      // stderr in red.
      process.stderr.write("\u001b[91m" + result.stderr + "\u001b[0m");
    }
    return result;
  }

  async close(): Promise<void> {
    if (this.pty !== null) {
      try {
        await this.pty.kill();
      } catch {
        // Ignore — we're tearing down anyway.
      }
    }
  }
}

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
 * Create a Python sandbox, retrying transient 500s (create is not auto-retried).
 *
 * `runtime` must be a Python runtime (the driver launches `python3`).
 */
async function createSandbox(
  name: string,
  instanceType: string,
  runtime: string,
  timeoutMs: number,
): Promise<Sandbox> {
  let lastErr: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await Sandbox.create({
        name,
        instanceType,
        runtime,
        timeout: timeoutMs,
      });
    } catch (err) {
      lastErr = err;
      if (attempt === 2) throw err;
      console.log(`create failed (${err}); retrying...`);
      await sleep(2 ** attempt * 1000);
    }
  }
  throw new Error("unreachable", { cause: lastErr });
}

interface Args {
  apiKey?: string;
  name: string;
  instanceType: string;
  runtime: string;
  timeoutMs: number;
}

function parseArgs(argv: string[]): Args {
  const args: Args = {
    name: "code-interpreter",
    instanceType: "cpu-1",
    runtime: "python313",
    timeoutMs: 30 * 60 * 1000,
  };
  for (let i = 0; i < argv.length; i++) {
    const [flag, inlineValue] = argv[i].split(/=(.*)/s);
    const value = () => (inlineValue !== undefined ? inlineValue : argv[++i]);
    switch (flag) {
      case "--api-key":
        args.apiKey = value();
        break;
      case "--name":
        args.name = value();
        break;
      case "--instance-type":
        args.instanceType = value();
        break;
      case "--runtime":
        args.runtime = value();
        break;
      case "--timeout-ms":
        args.timeoutMs = Number(value());
        break;
      default:
        throw new Error(`Unknown argument: ${flag}`);
    }
  }
  return args;
}

async function main(args: Args): Promise<void> {
  Sandbox.configure({ apiKey: resolveApiKey(args.apiKey) });

  console.log(
    `Creating sandbox '${args.name}' (${args.instanceType}, ${args.runtime})`,
  );
  const sandbox = await createSandbox(
    args.name,
    args.instanceType,
    args.runtime,
    args.timeoutMs,
  );

  const interpreter = new SandboxInterpreter(sandbox);
  try {
    console.log(`Sandbox ${sandbox.sandboxId} is running; starting interpreter`);
    await interpreter.start();
    console.log("Interpreter ready.\n");

    // Now we can execute some code in the Sandbox!
    console.log("--- hello, world ---");
    await interpreter.runCode("print('hello, world!')"); // hello, world!

    // The Sandbox and our code interpreter are stateful, so we can define
    // variables and use them in subsequent code.
    console.log("\n--- stateful variables ---");
    await interpreter.runCode("x = 10");
    await interpreter.runCode("y = 5");
    await interpreter.runCode("result = x + y");
    await interpreter.runCode("print(f'The result is: {result}')"); // The result is: 15

    // We can also see errors when code fails.
    console.log("\n--- error handling ---");
    await interpreter.runCode("print('Attempting to divide by zero...')");
    await interpreter.runCode("1 / 0"); // Execution Error: division by zero

    console.log("\nDone.");
  } finally {
    // Finally, let's clean up after ourselves and terminate the Sandbox.
    await interpreter.close();
    console.log(`\nTerminating sandbox ${sandbox.sandboxId}`);
    await sandbox.delete();
  }
}

main(parseArgs(process.argv.slice(2))).catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
