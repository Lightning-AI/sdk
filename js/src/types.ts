/**
 * Types for the Sandbox SDK public API and configuration.
 */

export interface SandboxConfig {
  /** API key (falls back to `LIGHTNING_API_KEY`). */
  apiKey?: string;
  /** Lightning Cloud base URL (falls back to `LIGHTNING_CLOUD_URL`, then production). */
  baseUrl?: string;
  /** Default organization ID for requests when not passed per call. */
  organizationId?: string;
}

/** Raw sandbox record returned by the Lightning API (camelCase JSON). */
export interface SandboxData {
  id: string;
  name: string;
  organizationId: string;
  clusterId: string;
  instanceType: string;
  spot: boolean;
  status: string;
  cloudspaceId: string;
  ports: string[];
  runtime: string;
  createdAt: string;
  updatedAt: string;
  /**
   * Whether the sandbox persists its filesystem across stops/idle via
   * automatic snapshots. See {@link CreateSandboxParams.persistent}.
   */
  persistent: boolean;
  /** Project the sandbox belongs to (empty when not scoped to a project). */
  projectId: string;
}

export interface CreateSandboxParams {
  name?: string;
  instanceType: string;
  spot?: boolean;
  ports?: number[];
  organizationId?: string;
  clusterId?: string;
  cloudspaceId?: string;
  runtime?: string;
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
  /**
   * Project the sandbox is owned by. Recommended for persistent sandboxes —
   * the controlplane scopes the auto-snapshot bucket prefix to it.
   */
  projectId?: string;
  /** Maximum duration in milliseconds before the sandbox is auto-stopped. */
  timeout?: number;
}

/** Parameters for resuming a stopped/paused persistent sandbox by id. */
export interface ResumeSandboxParams {
  sandboxId: string;
  organizationId?: string;
}

/** Options for {@link Sandbox.stop}. */
export interface StopSandboxOptions {
  /**
   * Project the auto-snapshot is written under for persistent sandboxes.
   * Defaults to the sandbox's original project when unset.
   */
  projectId?: string;
}

/** Options for {@link Sandbox.createSnapshot}. */
export interface CreateSnapshotParams {
  /**
   * Project the snapshot is stored under. Required by the platform —
   * snapshots are stored in the cluster bucket under the project's prefix
   * and authorization is project-scoped. Falls back to the sandbox's own
   * `projectId` when omitted.
   */
  projectId?: string;
  /** Tar exclude override for this snapshot. Platform default applies when unset. */
  excludes?: string[];
  /**
   * Expiration in milliseconds. Platform default applies when unset; pass `0`
   * to request no expiration.
   */
  expiration?: number;
}

/** A point-in-time snapshot of a sandbox's filesystem. */
export interface SnapshotData {
  id: string;
  organizationId: string;
  projectId: string;
  sourceSandboxId: string;
  /** `saving` | `ready` | `failed`. Only `ready` snapshots are restorable. */
  status: string;
  sizeBytes: number;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
  runtime: string;
}

export interface ListSnapshotsParams {
  organizationId?: string;
  projectId?: string;
  name?: string;
  pageToken?: string;
  limit?: number;
}

export interface GetSandboxParams {
  sandboxId: string;
  organizationId?: string;
}

export interface ListSandboxesParams {
  organizationId?: string;
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
  sudo?: boolean;
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
  /**
   * Cluster the sandbox is running on. Required because the controlplane
   * attach endpoint is keyed on `(clusterId, sandboxId)`.
   */
  clusterId: string;

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
