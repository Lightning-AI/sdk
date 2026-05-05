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
  name: string;
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

export interface CommandResult {
  cmdId: string;
  output: string;
  exitCode: number;
}

export interface CommandStatus {
  output: string;
  exitCode: number;
  running: boolean;
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
