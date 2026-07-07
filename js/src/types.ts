/**
 * Types for the Sandbox SDK public API and configuration.
 */
import type { V1NetworkPolicy } from "./lightning_cloud/openapi/data-contracts.js";
import type { NetworkPolicy, NetworkPolicyInput } from "./network-policy.js";

export interface SandboxConfig {
  /** API key (falls back to `LIGHTNING_SANDBOX_API_KEY`, then `LIGHTNING_API_KEY`). */
  apiKey?: string;
  /** Lightning Cloud base URL (falls back to `LIGHTNING_CLOUD_URL`, then production). */
  baseUrl?: string;
}

/** Raw sandbox record returned by the Lightning API (camelCase JSON). */
export interface SandboxData {
  id: string;
  name: string;
  /** Organization the sandbox belongs to (derived from the API key; read-back only). */
  organizationId: string;
  /** Cluster placement. Internal plumbing for PTY attach; not a user-facing field. */
  clusterId: string;
  instanceType: string;
  spot: boolean;
  status: string;
  ports: string[];
  /**
   * Public HTTPS URLs for the sandbox's exposed ports, keyed by port number.
   * Populated when the sandbox was created with `ports`; empty otherwise.
   */
  portUrls: Record<string, string>;
  runtime: string;
  /** Custom OCI image the sandbox was created with (`""` for a curated runtime). */
  image: string;
  /** Project Docker-registry Secret used to pull `image` (`""` when unused). */
  imageSecretRef: string;
  /** Source snapshot this sandbox was restored from (`""` otherwise). */
  snapshotId: string;
  /** User who created the sandbox (`""` if not tracked). */
  userId: string;
  createdAt: string;
  updatedAt: string;
  /**
   * Whether the sandbox persists its filesystem across stops/idle via
   * automatic snapshots. See {@link CreateSandboxParams.persistent}.
   */
  persistent: boolean;
  /** Project the sandbox belongs to (empty when not scoped to a project). */
  projectId: string;
  /** Writable disk size in GB (0 when inheriting the instance-type default). */
  storageGb: number;
  /** Maximum lifetime in milliseconds (0 = no timeout). */
  timeout: number;
  /** Raw egress policy as returned by the API (undefined = open egress). */
  networkPolicy?: V1NetworkPolicy;
  /**
   * Cluster machine the sandbox is (or was last) placed on. **Internal-only:**
   * the control plane returns this only to internal Lightning users
   * (`user.details.internal=true`) on create/get/list — `""` for external API
   * keys and for sandboxes created before the field landed. Used to attribute
   * create/TTI performance to specific hosts. See {@link Sandbox.machineId}.
   */
  machineId: string;
  /**
   * Per-phase wall-clock breakdown of the create flow. **Internal-only and
   * create-only:** populated solely on the {@link Sandbox.create} response and
   * solely for internal Lightning users; always `undefined` for external API
   * keys and on get/list. See {@link Sandbox.phaseDurations}.
   */
  phaseDurations?: SandboxPhaseDuration[];
}

/**
 * One per-phase wall-clock observation from the sandbox create flow.
 * Part of the internal-only {@link SandboxData.phaseDurations} breakdown.
 */
export interface SandboxPhaseDuration {
  /**
   * Namespaced phase id. `cp.*` phases are the control plane's own stopwatch
   * (e.g. `cp.total`, `cp.db_persist`); `agent.*` phases are the node agent's
   * litvisor-side breakdown (e.g. `agent.runsc.run`, `agent.image.ensure`).
   */
  phase: string;
  /** Wall-clock duration of the phase, in milliseconds. */
  durationMs: number;
}

export interface CreateSandboxParams {
  name?: string;
  instanceType: string;
  spot?: boolean;
  ports?: number[];
  runtime?: string;
  /**
   * Custom OCI image reference for the rootfs (e.g.
   * `"ghcr.io/myorg/img:latest"`). Mutually exclusive with `runtime`; CPU
   * sandboxes only.
   */
  image?: string;
  /**
   * Name of a project-scoped Docker-registry Secret used to pull a private
   * `image`. Only valid together with `image`.
   */
  imageSecretRef?: string;
  /**
   * Egress firewall policy, applied at create time only. Omit for open egress
   * (`"allow-all"`), pass `"deny-all"`, or a {@link NetworkPolicy} CIDR
   * allowlist.
   */
  networkPolicy?: NetworkPolicyInput;
  /**
   * Whether the sandbox persists its state across restarts via automatic
   * snapshots. Defaults to the platform default (currently `true`) when
   * omitted.
   *
   * When `true`, the controlplane automatically snapshots the sandbox on
   * idle, sleep, or eviction and transparently restores it the next time the
   * sandbox id is accessed — making the sandbox id a durable handle. Pair
   * with {@link Sandbox.stop} to pause (capturing an auto-snapshot) and
   * {@link Sandbox.resume} to bring it back by id.
   *
   * When `false`, the sandbox is best-effort ephemeral: state is lost on
   * stop, idle reclaim, or host reschedule.
   */
  persistent?: boolean;
  /**
   * Create the sandbox from an existing snapshot id (see
   * {@link Sandbox.createSnapshot}). The new sandbox boots with the snapshot's
   * filesystem.
   */
  snapshotId?: string;
  /** Maximum duration in milliseconds before the sandbox is auto-stopped. */
  timeout?: number;
  /**
   * Override for the sandbox's writable disk size, in GB. CPU sandboxes only.
   * When omitted the sandbox inherits the instance-type default (≈5 GB for
   * `cpu-1`; 10 / 40 / 60 / 80 GB for `cpu-2` / `cpu-4` / `cpu-8` / `cpu-16`).
   */
  storageGb?: number;
}

/** Parameters for resuming a stopped/paused persistent sandbox by id. */
export interface ResumeSandboxParams {
  sandboxId: string;
}

/** Options for {@link Sandbox.createSnapshot}. */
export interface CreateSnapshotParams {
  /** Tar exclude override for this snapshot. Platform default applies when unset. */
  excludes?: string[];
  /**
   * Expiration in milliseconds. Platform default applies when unset; pass `0`
   * to request no expiration.
   */
  expiration?: number;
  /**
   * Poll until the snapshot reaches `ready` before resolving. Defaults to
   * `true`; pass `false` to return the `saving` row immediately.
   */
  wait?: boolean;
  /** Max time in ms to wait for `ready` when `wait` is true. Defaults to 600000. */
  waitTimeoutMs?: number;
}

/** A point-in-time snapshot of a sandbox's filesystem. */
export interface SnapshotData {
  id: string;
  organizationId: string;
  projectId: string;
  sourceSandboxId: string;
  /** Source sandbox's name at capture time (`""` if not recorded). */
  sourceSandboxName: string;
  /** Source sandbox's instance type at capture time (`""` if not recorded). */
  sourceSandboxInstanceType: string;
  /** `saving` | `ready` | `failed`. Only `ready` snapshots are restorable. */
  status: string;
  sizeBytes: number;
  /** Snapshot creation time (parsed to a `Date`, matching {@link SandboxData}). */
  createdAt: Date;
  /** Snapshot last-update time (parsed to a `Date`). */
  updatedAt: Date;
  /** Expiry time as a `Date`, or `null` when the snapshot never expires. */
  expiresAt: Date | null;
  runtime: string;
  /** Resolved runtime image reference (`""` if not recorded). */
  runtimeImage: string;
  /** Content digest of the snapshot rootfs (`""` if not recorded). */
  rootfsDigest: string;
  /** Paths excluded from the snapshot tarball. */
  excludes: string[];
  /** `true` for control-plane auto-snapshots (persistent stop); `false` for user snapshots. */
  auto: boolean;
}

export interface ListSnapshotsParams {
  name?: string;
  pageToken?: string;
  limit?: number;
  /** Order by creation time: `"asc"` (oldest first) or `"desc"` (newest first). */
  sortOrder?: "asc" | "desc";
}

export interface GetSandboxParams {
  sandboxId: string;
}

export interface ListSandboxesParams {
  pageToken?: string;
  limit?: number;
}

export interface ListSandboxesResponse {
  sandboxes: SandboxData[];
  nextPageToken?: string;
  previousPageToken?: string;
  totalSize?: number;
}

export interface RunCommandOpts {
  cmd: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  detached?: boolean;
}

export interface CommandStatus {
  output: string;
  exitCode: number;
  /**
   * `true` while the command is still executing; `false` once it has exited.
   *
   * Synchronous (non-`detached`) commands return ``false`` here once
   * {@link Sandbox.runCommand} resolves. To check whether a `detached` command
   * is still running, fetch its status via {@link Sandbox.getCommand} (or block
   * until completion with {@link Sandbox.waitForCommand}).
   */
  running: boolean;
}

export interface WaitForCommandOptions {
  /** Maximum time to wait in milliseconds. Defaults to no timeout. */
  timeoutMs?: number;
  /** Time between polls in milliseconds. Defaults to 500ms. */
  pollIntervalMs?: number;
}

export interface CommandLog {
  timestamp: string;
  message: string;
}

export interface WriteFileParams {
  path: string;
  content: string;
}

export interface ReadFileParams {
  path: string;
}

export interface CreateDirectoryParams {
  path: string;
}

export interface FileStat {
  /** File type from `%F` (e.g. `regular file`, `directory`, `symbolic link`). */
  fileType: string;
  size: number;
  mtime: Date;
  /** Permission bits as an octal string (e.g. `644`). */
  mode: string;
}

// ---------------------------------------------------------------------------
// PTY (interactive shell) types
// ---------------------------------------------------------------------------

/** Terminal dimensions in columns and rows. */
export interface PtySize {
  cols: number;
  rows: number;
}

/** Parameters for creating a new PTY session. */
export interface PtyCreateOpts {
  /**
   * Caller-chosen identifier for the session. Re-using the same name with
   * `connectPty` reattaches to the same WebSocket-side session within the
   * SDK process (cross-process persistence requires a server follow-up).
   */
  sessionName: string;
  /** Working directory the session starts in. Sent as `cd ... && clear`. */
  cwd?: string;
  /** Environment variables exported in the session before any user input. */
  envs?: Record<string, string>;
  /** Initial terminal columns. Defaults to 80. */
  cols?: number;
  /** Initial terminal rows. Defaults to 24. */
  rows?: number;
  /**
   * Callback invoked for every chunk of bytes received from the shell
   * (combined stdout/stderr). Bytes are delivered exactly as the server
   * forwards them, with no buffering or line-splitting on the SDK side.
   */
  onData?: (data: Uint8Array) => void;
}

/** Parameters for connecting to an existing PTY session. */
export interface PtyConnectOpts {
  /** See {@link PtyCreateOpts.onData}. */
  onData?: (data: Uint8Array) => void;
}

/** Result returned when a PTY session terminates. */
export interface PtyResult {
  /**
   * Exit code of the underlying process. The Lightning xterm wire protocol
   * does not currently propagate the SSH command's exit status, so this is
   * `0` for a clean WebSocket close, `-1` for an abnormal close, and `null`
   * if the session is still running.
   */
  exitCode: number | null;
  /** Termination reason for abnormal exits. */
  error: string | null;
}

/** Snapshot of a PTY session's state. */
export interface PtySessionInfo {
  /** The session id supplied when the session was created. */
  id: string;
  /** Whether a WebSocket is currently attached to the session. */
  active: boolean;
  /** Terminal columns. */
  cols?: number;
  /** Terminal rows. */
  rows?: number;
  /** Working directory the session was created with. */
  cwd?: string;
  /** ISO timestamp the session was created. */
  createdAt?: string;
  /** Underlying process id, when available. */
  processId?: number;
}
