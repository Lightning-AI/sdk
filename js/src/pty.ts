import type { PtyResult, PtySessionInfo, PtySize } from "./types.js";

/**
 * Default `onData` sink: write raw shell bytes to `process.stdout`.
 *
 * Mirrors the Python SDK's `write_to_stdout` helper. On a TTY,
 * Node flushes per chunk, so users see live shell output without
 * having to wire up their own callback. Pass `onData: () => {}`
 * (or any no-op) to suppress.
 */
export function writeToStdout(chunk: Uint8Array): void {
  if (typeof process !== "undefined" && process.stdout && typeof process.stdout.write === "function") {
    process.stdout.write(chunk);
  }
}

/**
 * Live handle to a sandbox PTY (pseudo-terminal) session.
 *
 * A `PtyHandle` wraps a single WebSocket to the controlplane's
 * `/v1/clusters/{clusterId}/machines/{sandboxId}/attach` endpoint. Text
 * frames from the server are raw shell bytes (combined stdout/stderr); the
 * SDK forwards them verbatim to the `onData` callback supplied at create
 * time. Outbound input is sent as raw text frames; resize is sent as a
 * JSON control frame `{"type":"resize","cols":N,"rows":M}` (matches the
 * wire shape the Lightning UI's terminal already speaks).
 *
 * The handle is created by `Sandbox.process.createPty` / `connectPty` and
 * is not intended to be constructed directly.
 */
export class PtyHandle {
  /**
   * No-op `onData` sink used to opt out of the default {@link writeToStdout}
   * behavior. Pass `onData: PtyHandle.discard` to suppress live output.
   */
  static discard(_chunk: Uint8Array): void {}

  /** Caller-supplied session id (passed as `sessionName` query param). */
  readonly id: string;

  /**
   * Raw output callback. Defaults to {@link writeToStdout} so omitting
   * `onData` produces live output on a TTY (mirrors Python's default).
   */
  private readonly onDataCb: (data: Uint8Array) => void;

  private readonly ws: WebSocket;

  private _exitCode: number | null = null;
  private _error: string | null = null;
  private _size: PtySize;
  private _connected = false;
  private _closed = false;

  /**
   * Resolves once the WebSocket transitions to OPEN. Rejected if the
   * underlying socket errors out before opening.
   */
  private readonly openPromise: Promise<void>;

  /**
   * Resolves once the WebSocket has closed. Carries the populated
   * exit code / error so {@link wait} can be re-awaited safely.
   */
  private readonly closePromise: Promise<PtyResult>;

  /** Internal: assembled by `SandboxProcess` once it has built the URL. */
  constructor(opts: {
    id: string;
    ws: WebSocket;
    cols: number;
    rows: number;
    onData?: (data: Uint8Array) => void;
    /**
     * Lines of shell input automatically sent right after the connection
     * opens — typically `cd $cwd && clear` and any `export X=Y` lines.
     */
    initialInput?: string[];
  }) {
    this.id = opts.id;
    // Default to flushing stdout so JS users get the same live-output
    // experience Python users get from `write_to_stdout` on a TTY.
    this.onDataCb = opts.onData ?? writeToStdout;
    this.ws = opts.ws;
    this._size = { cols: opts.cols, rows: opts.rows };

    // Force binary frames to ArrayBuffer in Node so we can construct a
    // Uint8Array directly without going through Blob.arrayBuffer().
    this.ws.binaryType = "arraybuffer";

    let openResolve!: () => void;
    let openReject!: (err: Error) => void;
    this.openPromise = new Promise<void>((resolve, reject) => {
      openResolve = resolve;
      openReject = reject;
    });

    let closeResolve!: (r: PtyResult) => void;
    this.closePromise = new Promise<PtyResult>((resolve) => {
      closeResolve = resolve;
    });

    this.ws.addEventListener("open", () => {
      this._connected = true;
      // Drain any queued setup commands before the user can send input.
      if (opts.initialInput && opts.initialInput.length > 0) {
        for (const line of opts.initialInput) {
          try {
            this.ws.send(line);
          } catch {
            // Will be surfaced via the error handler below.
          }
        }
      }
      openResolve();
    });

    this.ws.addEventListener("message", (ev: MessageEvent) => {
      const chunk = toUint8Array(ev.data);
      if (chunk) this.onDataCb(chunk);
    });

    this.ws.addEventListener("error", () => {
      // The Node `ws` global delivers errors without details on the event;
      // we only know there was a problem. The close event fires next with
      // a numeric code we can use.
      if (!this._connected) {
        openReject(new Error("PTY WebSocket connection failed"));
      }
    });

    this.ws.addEventListener("close", (ev: CloseEvent) => {
      this._connected = false;
      this._closed = true;
      const clean = ev.code === 1000 || ev.code === 1005;
      this._exitCode = clean ? 0 : -1;
      if (!clean && ev.reason) this._error = ev.reason;
      else if (!clean) this._error = `WebSocket closed with code ${ev.code}`;
      closeResolve({ exitCode: this._exitCode, error: this._error });
    });
  }

  /** Most recent exit code; `null` while the session is still running. */
  get exitCode(): number | null {
    return this._exitCode;
  }

  /** Termination reason after an abnormal close; otherwise `null`. */
  get error(): string | null {
    return this._error;
  }

  /** Last terminal dimensions known to the SDK. */
  get size(): PtySize {
    return { ...this._size };
  }

  /**
   * Waits for the WebSocket to open. Useful before calling
   * {@link sendInput} so input doesn't race the handshake.
   *
   * ```ts
   * await ptyHandle.waitForConnection();
   * await ptyHandle.sendInput("ls -la\n");
   * ```
   *
   * @param timeoutMs reject if the socket hasn't opened within this many ms.
   */
  async waitForConnection(timeoutMs?: number): Promise<void> {
    if (this._connected) return;
    if (timeoutMs === undefined) {
      await this.openPromise;
      return;
    }
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_resolve, reject) => {
      timer = setTimeout(
        () => reject(new Error(`PTY connection timed out after ${timeoutMs}ms`)),
        timeoutMs,
      );
    });
    try {
      await Promise.race([this.openPromise, timeout]);
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  /** Whether the underlying WebSocket is currently OPEN. */
  isConnected(): boolean {
    return this._connected;
  }

  /**
   * Send input to the shell. Strings are forwarded verbatim; `Uint8Array`
   * values are decoded as UTF-8 (matches the existing handler, which
   * treats every WebSocket frame as text).
   *
   * ```ts
   * await ptyHandle.sendInput("ls -la\n");
   * await ptyHandle.sendInput(new Uint8Array([0x03])); // Ctrl+C
   * ```
   */
  async sendInput(data: string | Uint8Array): Promise<void> {
    if (this._closed) {
      throw new Error("PTY session is closed");
    }
    if (!this._connected) {
      await this.waitForConnection();
    }
    const payload = typeof data === "string" ? data : new TextDecoder().decode(data);
    this.ws.send(payload);
  }

  /**
   * Resize the terminal. Emits the same JSON control frame the Lightning
   * UI sends, which the server translates into an SSH `WindowChange`.
   *
   * ```ts
   * await ptyHandle.resize(120, 30);
   * ```
   */
  async resize(cols: number, rows: number): Promise<PtySessionInfo> {
    if (this._closed) {
      throw new Error("PTY session is closed");
    }
    if (!this._connected) {
      await this.waitForConnection();
    }
    this.ws.send(JSON.stringify({ type: "resize", cols, rows }));
    this._size = { cols, rows };
    return {
      id: this.id,
      active: this._connected,
      cols,
      rows,
    };
  }

  /**
   * Send Ctrl+C to the shell, then close the WebSocket. The remote screen
   * session (when present) keeps running; use
   * `Sandbox.process.killPtySession(id)` to also tear down the screen
   * session itself.
   */
  async kill(): Promise<void> {
    if (this._closed) return;
    try {
      if (this._connected) {
        this.ws.send("\u0003");
      }
    } catch {
      // Ignore — we're closing anyway.
    }
    await this.disconnect();
  }

  /**
   * Close the WebSocket without signaling the shell. The underlying
   * process keeps running on the server.
   */
  async disconnect(): Promise<void> {
    if (this._closed) return;
    try {
      this.ws.close(1000, "client disconnect");
    } catch {
      // Already closing.
    }
    await this.closePromise;
  }

  /**
   * Wait for the session to terminate. Resolves once the WebSocket has
   * closed (either because the user typed `exit`, the shell exited, or
   * the SDK called {@link disconnect}/{@link kill}).
   */
  async wait(): Promise<PtyResult> {
    return this.closePromise;
  }
}

/**
 * Best-effort coercion of a WebSocket message payload to bytes. The
 * Lightning xterm protocol always sends text frames; we still accept
 * Buffer / ArrayBuffer for forward compatibility.
 */
function toUint8Array(data: unknown): Uint8Array | undefined {
  if (typeof data === "string") {
    return new TextEncoder().encode(data);
  }
  if (data instanceof ArrayBuffer) {
    return new Uint8Array(data);
  }
  if (ArrayBuffer.isView(data)) {
    const view = data as ArrayBufferView;
    return new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
  }
  return undefined;
}
