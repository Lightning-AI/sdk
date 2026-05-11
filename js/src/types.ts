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
