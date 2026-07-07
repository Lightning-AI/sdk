import type {
  SandboxConfig,
  SandboxData,
  CreateSandboxParams,
  GetSandboxParams,
  ListSandboxesParams,
  ListSandboxesResponse,
  RunCommandOpts,
  CommandStatus,
  CommandLog,
  WaitForCommandOptions,
  WriteFileParams,
  ReadFileParams,
  CreateDirectoryParams,
  ResumeSandboxParams,
  CreateSnapshotParams,
  SnapshotData,
  ListSnapshotsParams,
  SandboxPhaseDuration,
} from "./types.js";
import { Command } from "./command.js";
import type {
  SandboxesServiceCreateSandboxDirectoryBody,
  SandboxesServiceCreateSandboxSnapshotBody,
  SandboxesServiceExtendSandboxTimeoutBody,
  SandboxesServiceRunSandboxCommandBody,
  SandboxesServiceStopSandboxBody,
  SandboxesServiceUpdateSandboxBody,
  SandboxesServiceWriteSandboxFileBody,
  V1CreateSandboxRequest,
  V1GetSandboxCommandLogsResponse,
  V1GetSandboxCommandResponse,
  V1GetSandboxFileResponse,
  V1ListSandboxCommandsResponse,
  V1ListSandboxesResponse,
  V1ListSandboxSnapshotsResponse,
  V1LogMessage,
  V1RunSandboxCommandResponse,
  V1Sandbox,
  V1SandboxCommand,
  V1SandboxSnapshot,
  V1StopSandboxResponse,
} from "./lightning_cloud/openapi/data-contracts.js";
import { getApiKey, getBaseUrl, mergeSandboxConfig } from "./config.js";
import { FileSystem } from "./filesystem.js";
import { SandboxProcess } from "./process.js";
import { NetworkPolicy, fromV1NetworkPolicy, toV1NetworkPolicy } from "./network-policy.js";

function buildQuery(params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, v);
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  apiKeyOverride?: string,
): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${getApiKey(apiKeyOverride)}`,
  };
  const init: RequestInit = { method, headers };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const resp = await fetch(url, init);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Lightning API error ${resp.status}: ${text}`);
  }

  const contentType = resp.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await resp.json()) as T;
  }
  return {} as T;
}

function toSandboxData(v: V1Sandbox): SandboxData {
  return {
    id: v.id ?? "",
    name: v.name ?? "",
    organizationId: v.organizationId ?? "",
    clusterId: v.clusterId ?? "",
    instanceType: v.instanceType ?? "",
    spot: v.spot ?? false,
    status: v.status ?? "",
    ports: v.ports ?? [],
    portUrls: v.portUrls ?? {},
    runtime: v.runtime ?? "",
    image: v.image ?? "",
    imageSecretRef: v.imageSecretRef ?? "",
    snapshotId: v.snapshotId ?? "",
    userId: v.userId ?? "",
    createdAt: v.createdAt ?? "",
    updatedAt: v.updatedAt ?? "",
    persistent: v.persistent ?? false,
    projectId: v.projectId ?? "",
    storageGb: v.storageGb !== undefined && v.storageGb !== "" ? Number(v.storageGb) : 0,
    timeout: v.timeout !== undefined && v.timeout !== "" ? Number(v.timeout) : 0,
    networkPolicy: v.networkPolicy,
    machineId: v.machineId ?? "",
    // Internal-only, create-only: absent for external keys and on get/list,
    // so this stays undefined for them. The wire `durationMs` is an int64
    // string; surface it as a number.
    phaseDurations: v.phaseDurations?.map((p) => ({
      phase: p.phase ?? "",
      durationMs: p.durationMs !== undefined && p.durationMs !== "" ? Number(p.durationMs) : 0,
    })),
  };
}

function toSnapshotData(v: V1SandboxSnapshot): SnapshotData {
  return {
    id: v.id ?? "",
    organizationId: v.organizationId ?? "",
    projectId: v.projectId ?? "",
    sourceSandboxId: v.sourceSandboxId ?? "",
    sourceSandboxName: v.sourceSandboxName ?? "",
    sourceSandboxInstanceType: v.sourceSandboxInstanceType ?? "",
    status: v.status ?? "",
    sizeBytes: v.sizeBytes !== undefined && v.sizeBytes !== "" ? Number(v.sizeBytes) : 0,
    createdAt: new Date(v.createdAt ?? ""),
    updatedAt: new Date(v.updatedAt ?? ""),
    expiresAt: v.expiresAt ? new Date(v.expiresAt) : null,
    runtime: v.runtime ?? "",
    runtimeImage: v.runtimeImage ?? "",
    rootfsDigest: v.rootfsDigest ?? "",
    excludes: v.tarExcludes ?? [],
    auto: Boolean(v.sourceSandboxPersistent),
  };
}

/**
 * A sandbox is an isolated Linux environment you can create on demand.
 * Use it to run commands, read/write files, and manage the sandbox lifecycle.
 *
 * ```ts
 * import { Sandbox } from "@lightning-ai/sandbox";
 *
 * const sandbox = await Sandbox.create({
 *   name: "my-sandbox",
 *   instanceType: "gpu.small",
 * });
 *
 * const result = await sandbox.runCommand("echo", ["hello"]);
 * console.log(result.output);
 *
 * // Detached execution: returns immediately, await `wait()` to block until done.
 * const detachedCmd = await sandbox.runCommand({
 *   cmd: "sleep",
 *   args: ["5"],
 *   detached: true,
 * });
 * const finished = await detachedCmd.wait();
 * if (finished.exitCode !== 0) console.error("Something went wrong...");
 *
 * await sandbox.delete();
 * ```
 */
export class Sandbox {
  readonly sandboxId: string;
  readonly name: string;
  readonly organizationId: string;
  readonly instanceType: string;
  readonly spot: boolean;
  readonly status: string;
  readonly ports: string[];
  /**
   * Public HTTPS URLs for the sandbox's exposed ports, keyed by port number
   * (e.g. `"8080": "https://8080-<sandbox-id>-s.cloudspaces.litng.ai"`).
   * Populated when the sandbox was created with `ports`; empty otherwise.
   * Use {@link Sandbox.getPortUrl} to look up a single port.
   */
  readonly portUrls: Record<string, string>;

  /** Cluster placement, kept internally for PTY attach. Not exposed publicly. */
  private readonly _clusterId: string;
  readonly runtime: string;
  /** Custom OCI image the sandbox was created with (`""` for a curated runtime). */
  readonly image: string;
  /** Project Docker-registry Secret used to pull `image` (`""` when unused). */
  readonly imageSecretRef: string;
  /** Source snapshot this sandbox was restored from (`""` otherwise). */
  readonly snapshotId: string;
  /** User who created the sandbox (`""` if not tracked). */
  readonly userId: string;
  readonly persistent: boolean;
  readonly projectId: string;
  readonly storageGb: number;
  /** Maximum lifetime in milliseconds (0 = no timeout). */
  readonly timeout: number;
  /** Egress firewall policy in effect for the sandbox. */
  readonly networkPolicy: NetworkPolicy;
  /**
   * Cluster machine that placed this sandbox. **Internal-only:** `""` unless the
   * API key belongs to an internal Lightning user, since the control plane only
   * returns it to internal callers. See {@link SandboxData.machineId}.
   */
  readonly machineId: string;
  /**
   * Per-phase wall-clock breakdown of the create flow (`cp.*` control-plane +
   * `agent.*` node-agent phases). **Internal-only and create-only:** present
   * only on a {@link Sandbox.create} result for internal Lightning users;
   * `undefined` for external keys and on {@link Sandbox.get}/{@link Sandbox.list}.
   * See {@link SandboxData.phaseDurations}.
   */
  readonly phaseDurations?: SandboxPhaseDuration[];
  readonly createdAt: Date;
  readonly updatedAt: Date;

  /** Path-oriented file helpers that run commands inside the sandbox (see {@link FileSystem}). */
  readonly fs: FileSystem;

  /** Lazily-instantiated PTY namespace; see {@link Sandbox.process}. */
  private _process?: SandboxProcess;

  private constructor(data: SandboxData) {
    this.sandboxId = data.id;
    this.name = data.name;
    this.organizationId = data.organizationId;
    this._clusterId = data.clusterId;
    this.instanceType = data.instanceType;
    this.spot = data.spot;
    this.status = data.status;
    this.ports = data.ports ?? [];
    this.portUrls = data.portUrls ?? {};
    this.runtime = data.runtime ?? "";
    this.image = data.image ?? "";
    this.imageSecretRef = data.imageSecretRef ?? "";
    this.snapshotId = data.snapshotId ?? "";
    this.userId = data.userId ?? "";
    this.persistent = data.persistent ?? false;
    this.projectId = data.projectId ?? "";
    this.storageGb = data.storageGb ?? 0;
    this.timeout = data.timeout ?? 0;
    this.networkPolicy = fromV1NetworkPolicy(data.networkPolicy);
    this.machineId = data.machineId ?? "";
    this.phaseDurations = data.phaseDurations;
    this.createdAt = new Date(data.createdAt);
    this.updatedAt = new Date(data.updatedAt);
    this.fs = new FileSystem(this);
  }

  /**
   * Interactive process namespace for this sandbox: PTY sessions and
   * shell-style helpers. Mirrors Daytona's `sandbox.process` surface.
   *
   * ```ts
   * const pty = await sandbox.process.createPty({
   *   sessionName: "shell",
   *   onData: (chunk) => process.stdout.write(chunk),
   * });
   * await pty.sendInput("ls -la\n");
   * ```
   */
  get process(): SandboxProcess {
    if (!this._process) {
      this._process = new SandboxProcess({
        sandboxId: this.sandboxId,
        organizationId: this.organizationId,
        clusterId: this._clusterId,
        getApiKey: () => getApiKey(),
        getBaseUrl: () => getBaseUrl(),
        runCommand: (opts) => this.runCommand(opts),
      });
    }
    return this._process;
  }

  // ---------------------------------------------------------------------------
  // Global configuration
  // ---------------------------------------------------------------------------

  /**
   * Set global defaults used by all subsequent SDK calls.
   */
  static configure(config: SandboxConfig): void {
    mergeSandboxConfig(config);
  }

  // ---------------------------------------------------------------------------
  // Static CRUD methods
  // ---------------------------------------------------------------------------

  static async create(params: CreateSandboxParams): Promise<Sandbox> {
    if (params.runtime && params.image) {
      throw new Error("Pass only one of 'runtime' and 'image' (they are mutually exclusive).");
    }
    if (params.imageSecretRef && !params.image) {
      throw new Error("'imageSecretRef' is only valid together with 'image'.");
    }

    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const defaultName = `sandbox-${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}-${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;

    const body: V1CreateSandboxRequest = {
      name: params.name ?? defaultName,
      instanceType: params.instanceType,
      spot: params.spot ?? false,
      ports: (params.ports ?? []).map(String),
    };
    if (params.runtime) body.runtime = params.runtime;
    if (params.image) body.image = params.image;
    if (params.imageSecretRef) body.imageSecretRef = params.imageSecretRef;
    if (params.persistent !== undefined) body.persistent = params.persistent;
    if (params.snapshotId) body.snapshotId = params.snapshotId;
    if (params.timeout !== undefined) body.timeout = String(params.timeout);
    if (params.storageGb !== undefined) body.storageGb = String(params.storageGb);
    const policy = toV1NetworkPolicy(params.networkPolicy);
    if (policy !== undefined) body.networkPolicy = policy;

    const data = await request<V1Sandbox>("POST", "/v1/core/sandboxes", body);
    return Sandbox.waitForRunning(new Sandbox(toSandboxData(data)));
  }

  /**
   * Poll {@link Sandbox.get} until the sandbox reports `running`, throwing if
   * it enters a terminal state or the readiness deadline elapses. Shared by
   * {@link Sandbox.create} and {@link Sandbox.resume}.
   */
  private static async waitForRunning(initial: Sandbox): Promise<Sandbox> {
    // phaseDurations come back only on the create response; the poll below
    // re-fetches via get(), where the control plane omits them. Remember the
    // create-time breakdown so it survives onto whatever object we return.
    const createPhaseDurations = initial.phaseDurations;
    let sandbox = initial;
    const start = Date.now();
    const deadline = start + 300_000;
    while (sandbox.status !== "running") {
      if (
        sandbox.status === "error" ||
        sandbox.status === "stopped" ||
        sandbox.status === "shutdown"
      ) {
        throw new Error(`Sandbox entered terminal state: ${sandbox.status}`);
      }
      if (Date.now() >= deadline) {
        throw new Error(`Sandbox did not become ready (current status: ${sandbox.status})`);
      }
      const elapsed = Date.now() - start;
      const pollMs = elapsed < 5_000 ? 100 : 1_000;
      await new Promise((r) => setTimeout(r, pollMs));
      sandbox = await Sandbox.get({ sandboxId: sandbox.sandboxId });
    }
    if (createPhaseDurations?.length && !sandbox.phaseDurations?.length) {
      (sandbox as { phaseDurations?: SandboxPhaseDuration[] }).phaseDurations =
        createPhaseDurations;
    }
    return sandbox;
  }

  static async get(params: GetSandboxParams): Promise<Sandbox> {
    const data = await request<V1Sandbox>(
      "GET",
      `/v1/core/sandboxes/${encodeURIComponent(params.sandboxId)}`,
    );
    return new Sandbox(toSandboxData(data));
  }

  static async list(
    params: ListSandboxesParams = {},
  ): Promise<{
    sandboxes: Sandbox[];
    nextPageToken: string;
    previousPageToken: string;
    totalSize: number;
  }> {
    const qs = buildQuery({
      pageToken: params.pageToken,
      limit: params.limit !== undefined ? String(params.limit) : undefined,
    });
    const data = await request<V1ListSandboxesResponse>("GET", `/v1/core/sandboxes${qs}`);
    const raw: ListSandboxesResponse = {
      sandboxes: (data.sandboxes ?? []).map(toSandboxData),
      nextPageToken: data.nextPageToken,
      previousPageToken: data.previousPageToken,
      totalSize:
        data.totalSize !== undefined && data.totalSize !== ""
          ? Number(data.totalSize)
          : undefined,
    };
    return {
      sandboxes: (raw.sandboxes ?? []).map((s) => new Sandbox(s)),
      nextPageToken: raw.nextPageToken ?? "",
      previousPageToken: raw.previousPageToken ?? "",
      totalSize: raw.totalSize ?? 0,
    };
  }

  /**
   * Resume a previously stopped/paused persistent sandbox from its most
   * recent auto-snapshot, preserving the sandbox id. Blocks until the sandbox
   * is `running` again. A no-op (returns the running sandbox) when it is
   * already running; errors when the sandbox is not persistent or has no
   * resumable auto-snapshot.
   */
  static async resume(params: ResumeSandboxParams): Promise<Sandbox> {
    const body: SandboxesServiceUpdateSandboxBody = { resume: true };
    const data = await request<V1Sandbox>(
      "PATCH",
      `/v1/core/sandboxes/${encodeURIComponent(params.sandboxId)}`,
      body,
    );
    return Sandbox.waitForRunning(new Sandbox(toSandboxData(data)));
  }

  // ---------------------------------------------------------------------------
  // Static methods — snapshots
  // ---------------------------------------------------------------------------

  static async listSnapshots(
    params: ListSnapshotsParams = {},
  ): Promise<{
    snapshots: SnapshotData[];
    nextPageToken: string;
    previousPageToken: string;
    totalSize: number;
  }> {
    const qs = buildQuery({
      name: params.name,
      pageToken: params.pageToken,
      limit: params.limit !== undefined ? String(params.limit) : undefined,
      sortOrder: params.sortOrder,
    });
    const data = await request<V1ListSandboxSnapshotsResponse>(
      "GET",
      `/v1/core/sandboxes/snapshots${qs}`,
    );
    return {
      snapshots: (data.snapshots ?? []).map(toSnapshotData),
      nextPageToken: data.nextPageToken ?? "",
      previousPageToken: data.previousPageToken ?? "",
      totalSize:
        data.totalSize !== undefined && data.totalSize !== "" ? Number(data.totalSize) : 0,
    };
  }

  static async getSnapshot(snapshotId: string): Promise<SnapshotData> {
    const data = await request<V1SandboxSnapshot>(
      "GET",
      `/v1/core/sandboxes/snapshots/${encodeURIComponent(snapshotId)}`,
    );
    return toSnapshotData(data);
  }

  static async deleteSnapshot(snapshotId: string): Promise<void> {
    await request<unknown>(
      "DELETE",
      `/v1/core/sandboxes/snapshots/${encodeURIComponent(snapshotId)}`,
    );
  }

  // ---------------------------------------------------------------------------
  // Instance methods — networking
  // ---------------------------------------------------------------------------

  /**
   * Return the public URL for one of the sandbox's exposed ports.
   *
   * ```ts
   * const sandbox = await Sandbox.create({ instanceType: "cpu-1", ports: [8080] });
   * const url = sandbox.getPortUrl(8080);
   * // => "https://8080-<sandbox-id>-s.cloudspaces.litng.ai"
   * ```
   *
   * @throws If the sandbox does not expose `port` (it must be passed via
   *   `ports` at create time).
   */
  getPortUrl(port: number | string): string {
    const url = this.portUrls[String(port)];
    if (!url) {
      const exposed = this.ports.length ? this.ports.join(", ") : "none";
      throw new Error(
        `Sandbox ${this.sandboxId} has no URL for port ${port}. ` +
          `Exposed ports: ${exposed} (pass 'ports' when creating the sandbox).`,
      );
    }
    return url;
  }

  // ---------------------------------------------------------------------------
  // Instance methods — lifecycle
  // ---------------------------------------------------------------------------

  async delete(): Promise<void> {
    const qs = buildQuery({
      organizationId: this.organizationId || undefined,
    });
    await request<unknown>(
      "DELETE",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}${qs}`,
    );
  }

  /**
   * Stop the sandbox. For persistent sandboxes the controlplane first
   * captures an auto-snapshot keyed to the sandbox id (returned as
   * `autoSnapshotId`) so it can later be brought back via {@link Sandbox.resume}
   * without losing filesystem state. For non-persistent sandboxes the server
   * is simply stopped and no snapshot is taken.
   */
  async stop(): Promise<{ autoSnapshotId: string }> {
    const body: SandboxesServiceStopSandboxBody = {
      organizationId: this.organizationId || undefined,
    };
    if (this.projectId) {
      body.projectId = this.projectId;
    }
    const data = await request<V1StopSandboxResponse>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/stop`,
      body,
    );
    return { autoSnapshotId: data.autoSnapshotId ?? "" };
  }

  /**
   * Resume this sandbox by id (see {@link Sandbox.resume}). Returns a fresh
   * running {@link Sandbox} instance; the original handle is left unchanged.
   */
  async resume(): Promise<Sandbox> {
    return Sandbox.resume({ sandboxId: this.sandboxId });
  }

  /**
   * Push out this sandbox's auto-stop deadline by `timeoutMs` milliseconds.
   *
   * The create-time `timeout` sets the *initial* deadline and is fixed once the
   * sandbox exists; this is the only way to move it afterward. Call it
   * repeatedly (e.g. as a heartbeat) to keep a long-running sandbox alive.
   * `timeoutMs` is the number of milliseconds to **add** to the current
   * deadline and must be at least 1000 (1 second).
   *
   * The control plane returns no payload, so the local `timeout` field is left
   * unchanged; call {@link Sandbox.get} if you need fresh state.
   */
  async extendTimeout(timeoutMs: number): Promise<void> {
    if (timeoutMs < 1000) {
      throw new Error("extendTimeout requires timeoutMs >= 1000 (milliseconds).");
    }
    const body: SandboxesServiceExtendSandboxTimeoutBody = {
      timeout: String(timeoutMs),
      organizationId: this.organizationId || undefined,
    };
    await request<unknown>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/extend-timeout`,
      body,
    );
  }

  /**
   * Capture a user-initiated snapshot of this sandbox's filesystem. The
   * returned snapshot starts in `saving` and flips to `ready` once the
   * in-sandbox agent finishes uploading; use {@link Sandbox.getSnapshot} to
   * poll for `ready`, and {@link CreateSandboxParams.snapshotId} to boot a new
   * sandbox from it.
   */
  async createSnapshot(params: CreateSnapshotParams = {}): Promise<SnapshotData> {
    const body: SandboxesServiceCreateSandboxSnapshotBody = {
      organizationId: this.organizationId || undefined,
    };
    if (this.projectId) body.projectId = this.projectId;
    if (params.excludes) body.excludes = params.excludes;
    if (params.expiration !== undefined) body.expiration = String(params.expiration);
    const data = await request<V1SandboxSnapshot>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/snapshot`,
      body,
    );
    let snapshot = toSnapshotData(data);
    if (params.wait === false || snapshot.status === "ready") {
      return snapshot;
    }
    const deadline = Date.now() + (params.waitTimeoutMs ?? 600_000);
    while (snapshot.status !== "ready") {
      if (snapshot.status === "failed") {
        throw new Error(`Snapshot ${snapshot.id} failed to capture`);
      }
      if (Date.now() >= deadline) {
        throw new Error(
          `Snapshot ${snapshot.id} did not become ready (current status: ${snapshot.status})`,
        );
      }
      await new Promise((r) => setTimeout(r, 1_000));
      snapshot = await Sandbox.getSnapshot(snapshot.id);
    }
    return snapshot;
  }

  // ---------------------------------------------------------------------------
  // Instance methods — commands
  // ---------------------------------------------------------------------------

  /**
   * Run a command inside the sandbox.
   *
   * When called without `detached: true`, the server waits for the process to
   * exit and the returned {@link Command} has `exitCode` populated. When
   * `detached: true` is passed, the call returns immediately with `exitCode`
   * equal to `null`; await {@link Command.wait} to block until completion.
   */
  async runCommand(command: string, args?: string[]): Promise<Command>;
  async runCommand(opts: RunCommandOpts): Promise<Command>;
  async runCommand(
    commandOrOpts: string | RunCommandOpts,
    args?: string[],
  ): Promise<Command> {
    const body: SandboxesServiceRunSandboxCommandBody = {
      organizationId: this.organizationId || undefined,
    };

    let detached = false;
    if (typeof commandOrOpts === "string") {
      body.command = commandOrOpts;
      body.args = args ?? [];
    } else {
      body.command = commandOrOpts.cmd;
      body.args = commandOrOpts.args ?? [];
      if (commandOrOpts.cwd) body.cwd = commandOrOpts.cwd;
      if (commandOrOpts.env) body.env = commandOrOpts.env;
      if (commandOrOpts.detached !== undefined) {
        body.detached = commandOrOpts.detached;
        detached = commandOrOpts.detached;
      }
    }

    const data = await request<V1RunSandboxCommandResponse>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/commands`,
      body,
    );

    return new Command(this, {
      cmdId: data.cmdId ?? "",
      output: data.output ?? "",
      exitCode: detached ? null : (data.exitCode ?? 0),
    });
  }

  async getCommandLogs(cmdId: string): Promise<{ logs: CommandLog[] }> {
    const qs = buildQuery({
      organizationId: this.organizationId || undefined,
    });
    const data = await request<V1GetSandboxCommandLogsResponse>(
      "GET",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/commands/${encodeURIComponent(cmdId)}/logs${qs}`,
    );
    const logs = (data.logs ?? []).map((l: V1LogMessage) => ({
      timestamp: l.timestamp ?? "",
      message: l.message ?? "",
    }));
    return { logs };
  }

  async killCommand(cmdId: string): Promise<void> {
    const qs = buildQuery({
      organizationId: this.organizationId || undefined,
    });
    await request<unknown>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/commands/${encodeURIComponent(cmdId)}/kill${qs}`,
    );
  }

  async getCommand(cmdId: string): Promise<CommandStatus> {
    const qs = buildQuery({
      organizationId: this.organizationId || undefined,
    });
    const data = await request<V1GetSandboxCommandResponse & { running?: boolean }>(
      "GET",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/commands/${encodeURIComponent(cmdId)}${qs}`,
    );
    return {
      output: data.output ?? "",
      exitCode: data.exitCode ?? 0,
      running: data.running ?? false,
    };
  }

  /**
   * List commands the server has recorded for this sandbox. Each returned
   * {@link Command} handle carries the recorded command line plus `startedAt` /
   * `updatedAt` timestamps, and supports {@link Command.getStatus},
   * {@link Command.wait}, {@link Command.kill}, and {@link Command.logs}.
   */
  async listCommands(): Promise<Command[]> {
    const qs = buildQuery({
      organizationId: this.organizationId || undefined,
    });
    const data = await request<V1ListSandboxCommandsResponse>(
      "GET",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/commands${qs}`,
    );
    return (data.commands ?? []).map((c: V1SandboxCommand) => {
      const running = c.running ?? false;
      return new Command(this, {
        cmdId: c.id ?? "",
        output: c.output ?? "",
        exitCode: running ? null : (c.exitCode ?? 0),
        command: c.command ?? "",
        startedAt: c.createdAt ?? null,
        updatedAt: c.updatedAt ?? null,
      });
    });
  }

  /**
   * Poll {@link getCommand} until the command exits and return its final status.
   *
   * Useful after launching a background command with `detached: true`:
   *
   * ```ts
   * const r = await sandbox.runCommand({ cmd: "long-task", detached: true });
   * const status = await sandbox.getCommand(r.cmdId);
   * if (status.running) {
   *   const final = await sandbox.waitForCommand(r.cmdId);
   *   console.log(final.exitCode);
   * }
   * ```
   */
  async waitForCommand(cmdId: string, opts: WaitForCommandOptions = {}): Promise<CommandStatus> {
    const pollIntervalMs = opts.pollIntervalMs ?? 500;
    const deadline = opts.timeoutMs !== undefined ? Date.now() + opts.timeoutMs : undefined;

    while (true) {
      const status = await this.getCommand(cmdId);
      if (!status.running) return status;
      if (deadline !== undefined && Date.now() >= deadline) {
        throw new Error(`Timed out waiting for command ${cmdId} to finish`);
      }
      await new Promise((r) => setTimeout(r, pollIntervalMs));
    }
  }

  // ---------------------------------------------------------------------------
  // Instance methods — files
  // ---------------------------------------------------------------------------

  async writeFile(params: WriteFileParams): Promise<void> {
    const body: SandboxesServiceWriteSandboxFileBody = {
      organizationId: this.organizationId || undefined,
      path: params.path,
      content: params.content,
    };
    await request<unknown>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/files`,
      body,
    );
  }

  async readFile(params: ReadFileParams): Promise<string | null> {
    const qs = buildQuery({
      path: params.path,
      organizationId: this.organizationId || undefined,
    });
    try {
      const data = await request<V1GetSandboxFileResponse>(
        "GET",
        `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/files${qs}`,
      );
      return data.content ?? null;
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) {
        return null;
      }
      throw err;
    }
  }

  async writeFiles(files: WriteFileParams[]): Promise<void> {
    for (const file of files) {
      await this.writeFile(file);
    }
  }

  async createDirectory(params: CreateDirectoryParams): Promise<void> {
    const body: SandboxesServiceCreateSandboxDirectoryBody = {
      organizationId: this.organizationId || undefined,
      path: params.path,
    };
    await request<unknown>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/directories`,
      body,
    );
  }

  /**
   * Create a single directory via the directories API. Convenience alias for
   * {@link createDirectory} that takes a bare path. For nested creation
   * (`mkdir -p`), use the shell-based {@link FileSystem.mkdir} via `sandbox.fs`.
   */
  async mkdir(path: string): Promise<void> {
    return this.createDirectory({ path });
  }
}
