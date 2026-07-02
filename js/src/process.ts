import type { Command } from "./command.js";
import { PtyHandle } from "./pty.js";
import type {
  PtyConnectOpts,
  PtyCreateOpts,
  PtySessionInfo,
  RunCommandOpts,
} from "./types.js";

/**
 * Runtime context the `Sandbox` passes into a `SandboxProcess` so that
 * the PTY namespace can build URLs, authenticate, and shell out to
 * `runCommand` for session bookkeeping without importing the `Sandbox`
 * class directly (avoids a circular dependency).
 *
 * Internal — not part of the public API surface.
 */
export interface SandboxProcessContext {
  sandboxId: string;
  organizationId: string;
  /** Cluster the sandbox is placed on; the attach endpoint is keyed on it. */
  clusterId: string;
  /**
   * Returns the resolved API key. Mirrors the lazy lookup used by the
   * REST request helpers so that `Sandbox.configure` calls made after
   * the sandbox object was created are still honored.
   */
  getApiKey(): string;
  /** Returns the resolved base URL (with no trailing slash). */
  getBaseUrl(): string;
  /** Forwards to `Sandbox.runCommand`. */
  runCommand(opts: RunCommandOpts): Promise<Command>;
}

/**
 * `sandbox.process` — interactive shell sessions on a sandbox.
 *
 * Mirrors the Daytona PTY surface so existing code shaped around it
 * ports over with mechanical changes only. Under the hood, every method
 * either opens a WebSocket against the controlplane's
 * `/v1/clusters/{clusterId}/machines/{sandboxId}/attach` endpoint (which
 * is bridged to the in-sandbox SSH server at port 2222) or shells out to
 * `screen` via the existing `runCommand` REST API for session
 * bookkeeping.
 *
 * Within a single SDK process every method works against a local
 * registry. Cross-process session persistence (i.e. `connectPty` from
 * a fresh process to a session created elsewhere) requires the sandbox
 * runtime image to ship `screen` and the gliderlabs SSH login shell to
 * honor `LAI_TERM_SESSION_NAME` / `LAI_TERM_RESTORE` — both of which
 * are tracked as a follow-up to this initial parity work.
 */
export class SandboxProcess {
  private readonly ctx: SandboxProcessContext;

  /**
   * Live handles bound to this `SandboxProcess`, keyed by their
   * caller-chosen session name. Used by `connectPty` /
   * `getPtySessionInfo` / `killPtySession` / `resizePtySession` to find
   * an existing session before falling back to `screen -ls` over
   * `runCommand`.
   */
  private readonly handles = new Map<string, PtyHandle>();

  constructor(ctx: SandboxProcessContext) {
    this.ctx = ctx;
  }

  /**
   * Create a new PTY session on the sandbox.
   *
   * ```ts
   * const pty = await sandbox.process.createPty({
   *   sessionName: "build",
   *   cols: 120,
   *   rows: 30,
   *   onData: (chunk) => process.stdout.write(chunk),
   * });
   * await pty.waitForConnection();
   * await pty.sendInput("npm test\n");
   * const result = await pty.wait();
   * ```
   */
  async createPty(opts: PtyCreateOpts): Promise<PtyHandle> {
    return this.openPty({ ...opts, restore: false });
  }

  /**
   * Reattach to a PTY session that was previously created by `createPty`.
   *
   * ```ts
   * const pty = await sandbox.process.connectPty("build", {
   *   onData: (chunk) => process.stdout.write(chunk),
   * });
   * ```
   */
  async connectPty(
    sessionName: string,
    opts?: PtyConnectOpts,
  ): Promise<PtyHandle> {
    return this.openPty({
      sessionName,
      onData: opts?.onData,
      restore: true,
    });
  }

  /**
   * List PTY sessions on the sandbox. Implemented as a `screen -ls`
   * call via {@link runCommand} so no new server endpoint is required.
   * Returns the union of locally-tracked handles and remote `screen`
   * sessions; locally-tracked handles include live `cols`/`rows`.
   */
  async listPtySessions(): Promise<PtySessionInfo[]> {
    let remote: PtySessionInfo[] = [];
    try {
      const result = await this.ctx.runCommand({
        cmd: "screen",
        args: ["-ls"],
      });
      remote = parseScreenList(result.output);
    } catch {
      // `screen -ls` exits non-zero when there are no sessions; the SDK
      // treats that as an empty list rather than an error.
    }

    const merged = new Map<string, PtySessionInfo>();
    for (const info of remote) merged.set(info.id, info);
    for (const [id, handle] of this.handles) {
      const existing = merged.get(id);
      const size = handle.size;
      merged.set(id, {
        id,
        active: handle.isConnected(),
        cols: size.cols,
        rows: size.rows,
        cwd: existing?.cwd,
        createdAt: existing?.createdAt,
        processId: existing?.processId,
      });
    }
    return Array.from(merged.values());
  }

  /**
   * Look up a single PTY session.
   *
   * ```ts
   * const info = await sandbox.process.getPtySessionInfo("build");
   * console.log(info.active);
   * ```
   */
  async getPtySessionInfo(id: string): Promise<PtySessionInfo> {
    const sessions = await this.listPtySessions();
    const found = sessions.find((s) => s.id === id);
    if (!found) {
      throw new Error(`PTY session "${id}" not found`);
    }
    return found;
  }

  /**
   * Forcefully terminate a PTY session. Closes any live `PtyHandle` for
   * the session within this SDK process and runs
   * `screen -X -S {id} quit` on the sandbox so the remote screen
   * session (when present) is also torn down.
   */
  async killPtySession(id: string): Promise<void> {
    const handle = this.handles.get(id);
    if (handle) {
      await handle.kill();
      this.handles.delete(id);
    }
    try {
      await this.ctx.runCommand({
        cmd: "screen",
        args: ["-X", "-S", id, "quit"],
      });
    } catch {
      // No remote session existed, or `screen` is not in the runtime
      // image — either way, the local handle (if any) has been killed.
    }
  }

  /**
   * Resize the terminal of an active PTY session. Requires the session
   * to be currently attached in this SDK process; the existing wire
   * protocol carries resize as a JSON control frame on the open
   * WebSocket and offers no out-of-band REST equivalent.
   */
  async resizePtySession(
    id: string,
    cols: number,
    rows: number,
  ): Promise<PtySessionInfo> {
    const handle = this.handles.get(id);
    if (!handle || !handle.isConnected()) {
      throw new Error(
        `PTY session "${id}" is not attached in this process; resize requires an active connection`,
      );
    }
    return handle.resize(cols, rows);
  }

  /** Internal: builds the WebSocket URL and opens the connection. */
  private async openPty(args: {
    sessionName: string;

    cwd?: string;
    envs?: Record<string, string>;
    cols?: number;
    rows?: number;
    onData?: (data: Uint8Array) => void;
    restore: boolean;
  }): Promise<PtyHandle> {
    const cols = args.cols ?? 80;
    const rows = args.rows ?? 24;

    const url = new URL(
      `${this.ctx.getBaseUrl()}/v1/clusters/${encodeURIComponent(this.ctx.clusterId)}/machines/${encodeURIComponent(this.ctx.sandboxId)}/attach`,
    );
    // Switch http(s) -> ws(s).
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";

    url.searchParams.set("sessionName", args.sessionName ? args.sessionName : "main-session");
    url.searchParams.set("cols", String(cols));
    url.searchParams.set("rows", String(rows));
    if (args.restore) url.searchParams.set("restore", "true");

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.ctx.getApiKey()}`,
    };
    if (this.ctx.organizationId) {
      headers["X-Lightning-Organization-Id"] = this.ctx.organizationId;
    }

    const wsCtor = (globalThis as { WebSocket?: typeof WebSocket }).WebSocket;
    if (!wsCtor) {
      throw new Error(
        "Native WebSocket is not available; @lightningai/sdk requires Node 22+ for PTY support",
      );
    }

    // Node's native WebSocket constructor accepts a `headers` option in the
    // second argument as of Node 22; the DOM lib types it as `protocols`,
    // so we cast to bypass the lib mismatch without pulling in `@types/ws`.
    const ws = new (wsCtor as unknown as new (
      url: string,
      opts?: { headers?: Record<string, string> },
    ) => WebSocket)(url.toString(), { headers });
    const initialInput = buildInitialInput(args.cwd, args.envs);

    const handle = new PtyHandle({
      id: args.sessionName,
      ws,
      cols,
      rows,
      onData: args.onData,
      initialInput,
    });

    // Track in the local registry; remove when the session closes so a
    // subsequent createPty with the same sessionName doesn't see a stale entry.
    this.handles.set(args.sessionName, handle);
    handle.wait().finally(() => {
      const current = this.handles.get(args.sessionName);
      if (current === handle) this.handles.delete(args.sessionName);
    });

    return handle;
  }
}

/**
 * Build the lines that should be flushed to the shell right after the
 * WebSocket opens — `export X=Y` for each env var followed by an
 * optional `cd $cwd && clear`. Mirrors the Daytona convention so users
 * see a clean prompt at the requested directory.
 */
function buildInitialInput(
  cwd: string | undefined,
  envs: Record<string, string> | undefined,
): string[] {
  const lines: string[] = [];
  if (envs) {
    for (const [k, v] of Object.entries(envs)) {
      lines.push(`export ${k}=${shellQuote(v)}\n`);
    }
  }
  if (cwd) {
    lines.push(`cd ${shellQuote(cwd)} && clear\n`);
  }
  return lines;
}

/** Single-quote a value for safe inclusion in a POSIX shell command. */
function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

/**
 * Parse the (text) output of `screen -ls`. The format looks like:
 *
 *   There is a screen on:
 *           12345.build       (Detached)
 *   1 Socket in /run/screen/S-root.
 *
 * We extract the part after the first `.` (the user-supplied session
 * name) and infer `active` from the `(Attached)` / `(Detached)` tag.
 */
function parseScreenList(output: string): PtySessionInfo[] {
  const sessions: PtySessionInfo[] = [];
  for (const rawLine of output.split("\n")) {
    const line = rawLine.trim();
    // Lines starting with a digit and a dot are session entries;
    // everything else is header / footer noise.
    const match = line.match(/^(\d+)\.([^\s]+)\s*\((Attached|Detached)\)/);
    if (!match) continue;
    const [, pid, name, state] = match;
    sessions.push({
      id: name,
      active: state === "Attached",
      processId: Number(pid),
    });
  }
  return sessions;
}
