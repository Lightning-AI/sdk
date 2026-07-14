/// <reference types="node" />
/**
 * Run arbitrary code in a sandboxed environment.
 *
 * It demonstrates running many languages inside a single, isolated sandbox:
 * bash, Python, Node.js, Ruby, and PHP. It then pipes data between Python and
 * Node.js, streams output from a long-running process, and -- because the
 * sandbox is fully isolated from our machine -- runs some genuinely dangerous
 * code before tearing the sandbox down.
 *
 * A couple of notes on how it works:
 *
 *   * Lightning's curated runtimes ship *one* language each (a `python313` box
 *     has no `node`, a `node24` box has no `python`). So we start from `python313`
 *     (which already has Python + bash) and `apt-get install` the remaining
 *     runtimes (nodejs, ruby, php) into that same sandbox. This needs egress,
 *     which is on by default.
 *
 *   * `sandbox.runCommand(...)` runs synchronously and returns the full output
 *     once the process finishes -- which is all most steps here need. Synchronous
 *     calls have a ~120s server-side deadline, though, so for long-running work
 *     (the toolchain install) and for streaming a live process we launch the
 *     command *detached* and watch a file it writes (see `runAndWait`).
 *
 * Usage:
 *   # Provide your Lightning API key via the environment (recommended):
 *   export LIGHTNING_SANDBOX_API_KEY=sk-lit-...
 *   npx tsx arbitrary-code-sandbox.ts
 *
 *   # ...or pass it (and any other setting) explicitly:
 *   npx tsx arbitrary-code-sandbox.ts --api-key sk-lit-... --instance-type cpu-2
 */
import { randomUUID } from "node:crypto";
import { Sandbox } from "../src/index.js";

// Environment variables checked (in order) when --api-key is not passed.
const API_KEY_ENV_VARS = ["LIGHTNING_SANDBOX_API_KEY", "LIGHTNING_API_KEY"] as const;

const MINUTES_MS = 60 * 1000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// uuid4().hex equivalent: 32 hex chars, no dashes.
const hexToken = () => randomUUID().replace(/-/g, "");

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
 * Run a bash `script` in the sandbox and block until it exits.
 *
 * Returns `[exitCode, combinedOutput]`.
 *
 * This is the robust way to run *long* commands. A plain synchronous
 * `runCommand` has a ~120s server-side deadline, so long installs fail with a
 * 502; and while detached commands do run, the backend's command-*status*
 * endpoints don't reliably report their completion or output. So we launch the
 * script detached, redirect its combined output to a file, and have it drop an
 * exit-code "sentinel" file the moment it finishes -- then poll `readFile`
 * (which is reliable) until that sentinel appears.
 */
async function runAndWait(
  sandbox: Sandbox,
  script: string,
  { timeout, pollInterval = 2.0 }: { timeout: number; pollInterval?: number },
): Promise<[number, string]> {
  const token = hexToken();
  const outPath = `/tmp/.cmd_${token}.out`;
  const donePath = `/tmp/.cmd_${token}.done`;
  // Run the script in a subshell so the redirect captures all of it, then
  // record the exit code in the sentinel file the instant the subshell exits.
  const wrapped = `(\n${script}\n) >${outPath} 2>&1\necho $? >${donePath}\n`;
  await sandbox.runCommand({ cmd: "bash", args: ["-c", wrapped], detached: true });

  const deadline = Date.now() + timeout * 1000;
  while (Date.now() < deadline) {
    const exitCode = await sandbox.readFile({ path: donePath });
    if (exitCode && exitCode.trim()) {
      return [parseInt(exitCode.trim(), 10), (await sandbox.readFile({ path: outPath })) ?? ""];
    }
    await sleep(pollInterval * 1000);
  }
  throw new Error(`command did not finish within ${timeout}s`);
}

/**
 * Create a sandbox and install Node.js, Ruby and PHP alongside Python.
 *
 * Lightning runtimes ship a single language, so we start from a Python runtime
 * (Python + bash already present) and apt-get install the others into the same
 * box.
 */
async function setupMultiLanguageSandbox(args: Args): Promise<Sandbox> {
  console.log(`🏖️  Creating sandbox (${args.runtime} base)...`);

  // The SDK does not auto-retry create(), and it can occasionally fail with a
  // transient 500 -- wrap it in a short backoff retry.
  let sandbox: Sandbox | undefined;
  let lastErr: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      sandbox = await Sandbox.create({
        name: args.name,
        instanceType: args.instanceType,
        runtime: args.runtime,
        timeout: args.timeoutMs,
      });
      break;
    } catch (err) {
      lastErr = err;
      if (attempt === 2) throw err;
      console.log(`🏖️  create failed (${err}); retrying...`);
      await sleep(2 ** attempt * 1000);
    }
  }
  if (!sandbox) throw new Error("unreachable", { cause: lastErr });

  console.log(`Sandbox ID: ${sandbox.sandboxId}`);

  console.log("🏖️  Installing nodejs, ruby and php (this can take a minute)...");
  const installScript =
    "set -eux; " +
    "export DEBIAN_FRONTEND=noninteractive; " +
    "apt-get update; " +
    "apt-get install -y nodejs ruby php-cli";
  // The install takes longer than the synchronous deadline, so run it detached
  // and wait on its sentinel file.
  const [exitCode, output] = await runAndWait(sandbox, installScript, { timeout: 600 });
  if (exitCode !== 0) {
    throw new Error(`toolchain install failed (exit ${exitCode}):\n${output}`);
  }

  return sandbox;
}

/**
 * Run bash, Python, Node.js, Ruby and PHP in the sandbox.
 *
 * Each snippet is short, so we run them synchronously (one call each returns
 * the full output once the process exits).
 */
async function runInEachLanguage(sandbox: Sandbox): Promise<void> {
  console.log("\n--- Running bash, Python, Node.js, Ruby and PHP ---");

  const commands: [string, string[]][] = [
    ["bash", ["-c", "echo 'hello from bash'"]],
    ["python", ["-c", "print('hello from python')"]],
    ["node", ["-e", 'console.log("hello from nodejs")']],
    ["ruby", ["-e", "puts 'hello from ruby'"]],
    ["php", ["-r", "echo 'hello from php';"]],
  ];

  for (const [cmd, cmdArgs] of commands) {
    const result = await sandbox.runCommand(cmd, cmdArgs);
    console.log(result.output.replace(/\s+$/, ""));
  }
}

/**
 * Pipe data between Python and Node.js using bash.
 *
 * Python generates ten random numbers; Node.js reads them from stdin and
 * prints their sum.
 */
async function pipePythonIntoNode(sandbox: Sandbox): Promise<void> {
  console.log("\n--- Piping Python -> Node.js via bash ---");

  const combined = await sandbox.runCommand("bash", [
    "-c",
    `python -c 'import random; print(" ".join(str(random.randint(1, 100)) for _ in range(10)))' |
            node -e 'const readline = require("readline");
            const rl = readline.createInterface({input: process.stdin});
            rl.on("line", (line) => {
              const sum = line.split(" ").map(Number).reduce((a, b) => a + b, 0);
              console.log(\`The sum of the random numbers is: \${sum}\`);
              rl.close();
            });'`,
  ]);
  console.log(combined.output.trim());
}

/**
 * Stream output from a long-running process as it is produced.
 *
 * There's no stdout iterator for a running command (and the detached
 * command-status endpoints don't stream output), so we launch the process
 * detached with its output redirected to a file, then poll that file with
 * `readFile` and print only the newly-appended bytes each tick. Ruby flushes
 * stdout so the lines land in the file incrementally.
 */
async function streamLongRunningProcess(sandbox: Sandbox): Promise<void> {
  console.log("\n--- Streaming a long-running Ruby process ---");

  const rubyScript = `
    10.times do |i|
      puts "Line #{i + 1}: #{Time.now}"
      STDOUT.flush
      sleep(0.5)
    end
    `;
  // Write the script to a file to avoid nested shell quoting, then launch it
  // detached with output going to a file we can tail.
  await sandbox.writeFile({ path: "/root/slow_printer.rb", content: rubyScript });
  const token = hexToken();
  const outPath = `/tmp/.stream_${token}.out`;
  const donePath = `/tmp/.stream_${token}.done`;
  const wrapped = `ruby /root/slow_printer.rb >${outPath} 2>&1\necho $? >${donePath}\n`;
  await sandbox.runCommand({ cmd: "bash", args: ["-c", wrapped], detached: true });

  let printed = 0;
  while (true) {
    const output = (await sandbox.readFile({ path: outPath })) ?? "";
    if (output.length > printed) {
      process.stdout.write(output.slice(printed));
      printed = output.length;
    }
    if (((await sandbox.readFile({ path: donePath })) ?? "").trim()) break;
    await sleep(250);
  }
}

/** Run genuinely destructive code -- safe because the sandbox is isolated. */
async function runDangerousCode(sandbox: Sandbox): Promise<void> {
  console.log("\n--- Running dangerous code (rm -rf / inside the sandbox) ---");
  try {
    await sandbox.runCommand("rm", ["-rfv", "/", "--no-preserve-root"]);
  } catch (err) {
    // Wiping the filesystem can knock out the in-sandbox agent mid-command;
    // that's expected here since we're about to delete the sandbox anyway.
    console.log(`(sandbox stopped responding, as expected: ${err})`);
  }
  console.log("The sandbox filesystem has been wiped.");
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
    name: "example-safe-code-execution",
    instanceType: "cpu-1",
    runtime: "python313",
    timeoutMs: 30 * MINUTES_MS,
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

  const sandbox = await setupMultiLanguageSandbox(args);
  try {
    await runInEachLanguage(sandbox);
    await pipePythonIntoNode(sandbox);
    await streamLongRunningProcess(sandbox);
    await runDangerousCode(sandbox);
  } finally {
    // Clean up after ourselves -- remote sandboxes are not garbage-collected.
    console.log("\n🏖️  Terminating sandbox...");
    await sandbox.delete();
    console.log("Done.");
  }
}

main(parseArgs(process.argv.slice(2))).catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
