import { posix } from "node:path";

import {
  Sandbox,
  type CreateSandboxParams,
  type NetworkPolicyInput,
} from "@lightningai/sdk";
import type {
  SandboxBackend,
  SandboxBackendCreateInput,
  SandboxBackendHandle,
  SandboxNetworkPolicy,
  SandboxProcess,
  SandboxReadTextFileOptions,
  SandboxSession,
} from "eve/sandbox";

export interface LightningSandboxOptions {
  instanceType?: string;
  networkPolicy?: NetworkPolicyInput;
  storageGb?: number;
  timeout?: number;
}

const BACKEND_NAME = "lightning-ai";
const encoder = new TextEncoder();

export function lightningSandbox(options: LightningSandboxOptions = {}): SandboxBackend {
  return {
    name: BACKEND_NAME,

    async create(input) {
      const sandbox = await openSandbox(input, options);
      return createHandle(input, sandbox);
    },

    async prewarm(input) {
      if (input.bootstrap || input.seedFiles.length > 0) {
        throw new Error(
          "This concise Lightning backend does not implement Eve templates; " +
            "use on-session setup instead of sandbox bootstrap or workspace seeds.",
        );
      }
      return { reused: true };
    },
  };
}

async function openSandbox(
  input: SandboxBackendCreateInput,
  options: LightningSandboxOptions,
): Promise<Sandbox> {
  const existingId = input.existingMetadata?.sandboxId;
  if (typeof existingId === "string" && existingId) {
    try {
      const sandbox = await Sandbox.resume({ sandboxId: existingId });
      await ensureWorkspace(sandbox);
      return sandbox;
    } catch (error) {
      if (!isNotFound(error)) throw error;
    }
  }

  const params: CreateSandboxParams = {
    name: sandboxName(input.sessionKey),
    instanceType: options.instanceType ?? "cpu-1",
    persistent: true,
    networkPolicy: options.networkPolicy ?? "allow-all",
  };
  if (options.storageGb !== undefined) params.storageGb = options.storageGb;
  if (options.timeout !== undefined) params.timeout = options.timeout;
  const sandbox = await Sandbox.create(params);
  await ensureWorkspace(sandbox);
  return sandbox;
}

async function ensureWorkspace(sandbox: Sandbox): Promise<void> {
  const result = await sandbox.runCommand("mkdir", ["-p", "/workspace"]);
  assertCommandSucceeded(result.exitCode, result.output, "create /workspace");
}

function createHandle(
  input: SandboxBackendCreateInput,
  sandbox: Sandbox,
): SandboxBackendHandle {
  const session = createSession(sandbox);

  return {
    session,
    useSessionFn: async () => session,
    async captureState() {
      return {
        backendName: BACKEND_NAME,
        metadata: { sandboxId: sandbox.sandboxId },
        sessionKey: input.sessionKey,
      };
    },
    async shutdown() {
      const current = await Sandbox.get({ sandboxId: sandbox.sandboxId });
      if (current.status === "running") await current.stop();
    },
  };
}

function createSession(sandbox: Sandbox): SandboxSession {
  const resolvePath = (path: string) =>
    posix.isAbsolute(path) ? path : posix.resolve("/workspace", path);

  const spawn = async (options: Parameters<SandboxSession["spawn"]>[0]) => {
    throwIfAborted(options.abortSignal);
    const command = await sandbox.runCommand({
      cmd: "bash",
      args: ["-lc", options.command],
      cwd: resolvePath(options.workingDirectory ?? "."),
      env: options.env,
      detached: true,
    });
    return streamCommand(command, options.abortSignal);
  };

  const readBinaryFile = async (
    options: Parameters<SandboxSession["readBinaryFile"]>[0],
  ): Promise<Uint8Array | null> => {
    throwIfAborted(options.abortSignal);
    const path = resolvePath(options.path);
    if (!(await sandbox.fs.exists(path))) return null;

    const result = await sandbox.runCommand("base64", ["-w0", path]);
    assertCommandSucceeded(result.exitCode, result.output, `read ${path}`);
    throwIfAborted(options.abortSignal);
    return Buffer.from(result.output.trim(), "base64");
  };

  const writeBinaryFile = async (
    options: Parameters<SandboxSession["writeBinaryFile"]>[0],
  ): Promise<void> => {
    throwIfAborted(options.abortSignal);
    const path = resolvePath(options.path);
    const content = Buffer.from(options.content).toString("base64");
    const result = await sandbox.runCommand("bash", [
      "-lc",
      'mkdir -p -- "$(dirname -- "$1")" && printf %s "$2" | base64 -d > "$1"',
      "eve-write",
      path,
      content,
    ]);
    assertCommandSucceeded(result.exitCode, result.output, `write ${path}`);
    throwIfAborted(options.abortSignal);
  };

  return {
    id: sandbox.sandboxId,
    resolvePath,
    spawn,

    async run(options) {
      const process = await spawn(options);
      const [stdout, stderr, result] = await Promise.all([
        streamToText(process.stdout),
        streamToText(process.stderr),
        process.wait(),
      ]);
      return { ...result, stdout, stderr };
    },

    async readFile(options) {
      const bytes = await readBinaryFile(options);
      if (bytes === null) return null;
      return new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(bytes);
          controller.close();
        },
      });
    },

    readBinaryFile,

    async readTextFile(options) {
      const bytes = await readBinaryFile(options);
      if (bytes === null) return null;
      const text = Buffer.from(bytes).toString((options.encoding ?? "utf-8") as BufferEncoding);
      return selectLines(text, options);
    },

    async writeFile(options) {
      const bytes = await streamToBytes(options.content, options.abortSignal);
      await writeBinaryFile({ ...options, content: bytes });
    },

    writeBinaryFile,

    async writeTextFile(options) {
      const bytes = Buffer.from(
        options.content,
        (options.encoding ?? "utf-8") as BufferEncoding,
      );
      await writeBinaryFile({ ...options, content: bytes });
    },

    async removePath(options) {
      throwIfAborted(options.abortSignal);
      const path = resolvePath(options.path);
      const flags = `${options.recursive ? "r" : ""}${options.force ? "f" : ""}`;
      const result = await sandbox.runCommand("rm", [
        ...(flags ? [`-${flags}`] : []),
        "--",
        path,
      ]);
      assertCommandSucceeded(result.exitCode, result.output, `remove ${path}`);
    },

    async setNetworkPolicy(_policy: SandboxNetworkPolicy) {
      throw new Error(
        "Lightning sandbox network policy is fixed at creation time; " +
          "set networkPolicy in lightningSandbox(...).",
      );
    },
  };
}

function streamCommand(
  command: Awaited<ReturnType<Sandbox["runCommand"]>>,
  abortSignal?: AbortSignal,
): SandboxProcess {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let cancelled = false;
  let finished = false;
  let killPromise: Promise<void> | undefined;

  const stdout = new ReadableStream<Uint8Array>({
    start(value) {
      controller = value;
    },
    cancel() {
      cancelled = true;
    },
  });
  const stderr = new ReadableStream<Uint8Array>({
    start(value) {
      value.close();
    },
  });

  const kill = () => {
    if (finished) return Promise.resolve();
    return (killPromise ??= command.kill());
  };
  const onAbort = () => void kill();
  abortSignal?.addEventListener("abort", onAbort, { once: true });

  const waitPromise = (async () => {
    let previous = "";
    try {
      while (true) {
        throwIfAborted(abortSignal);
        const status = await command.getStatus();
        const delta = status.output.startsWith(previous)
          ? status.output.slice(previous.length)
          : status.output;
        previous = status.output;
        if (delta && !cancelled) controller.enqueue(encoder.encode(delta));
        if (!status.running) {
          finished = true;
          if (!cancelled) controller.close();
          return { exitCode: status.exitCode };
        }
        await delay(250, abortSignal);
      }
    } catch (error) {
      if (!cancelled) controller.error(error);
      throw error;
    } finally {
      abortSignal?.removeEventListener("abort", onAbort);
    }
  })();

  return {
    stdout,
    stderr,
    wait: () => waitPromise,
    kill,
  };
}

async function streamToBytes(
  stream: ReadableStream<Uint8Array>,
  abortSignal?: AbortSignal,
): Promise<Uint8Array> {
  const chunks: Uint8Array[] = [];
  let length = 0;
  const reader = stream.getReader();
  while (true) {
    throwIfAborted(abortSignal);
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    length += value.byteLength;
  }

  const output = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

async function streamToText(stream: ReadableStream<Uint8Array>): Promise<string> {
  return new TextDecoder().decode(await streamToBytes(stream));
}

function selectLines(text: string, options: SandboxReadTextFileOptions): string {
  const { startLine, endLine } = options;
  if (startLine === undefined && endLine === undefined) return text;
  if (startLine !== undefined && (!Number.isInteger(startLine) || startLine < 1)) {
    throw new Error("startLine must be a positive integer");
  }
  if (endLine !== undefined && (!Number.isInteger(endLine) || endLine < 1)) {
    throw new Error("endLine must be a positive integer");
  }
  if (startLine !== undefined && endLine !== undefined && startLine > endLine) {
    throw new Error("startLine must not be greater than endLine");
  }

  const lines = text.match(/.*(?:\r\n|\n|\r|$)/g)?.filter(Boolean) ?? [];
  return lines.slice((startLine ?? 1) - 1, endLine).join("");
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw signal.reason ?? new DOMException("Aborted", "AbortError");
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function assertCommandSucceeded(
  exitCode: number | null,
  output: string,
  action: string,
): void {
  if (exitCode === 0) return;
  throw new Error(`${action} failed (exit ${exitCode ?? "unknown"}): ${output.trim()}`);
}

function sandboxName(sessionKey: string): string {
  return `eve-${sessionKey}`.replaceAll(/[^a-zA-Z0-9._-]/g, "-").slice(0, 63);
}

function isNotFound(error: unknown): boolean {
  return error instanceof Error && /\b404\b/.test(error.message);
}
