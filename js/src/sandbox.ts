import type {
  SandboxConfig,
  SandboxData,
  CreateSandboxParams,
  GetSandboxParams,
  ListSandboxesParams,
  ListSandboxesResponse,
  RunCommandOpts,
  CommandResult,
  CommandStatus,
  CommandLog,
  WriteFileParams,
  ReadFileParams,
  CreateDirectoryParams,
} from "./types.js";
import type {
  SandboxesServiceCreateSandboxDirectoryBody,
  SandboxesServiceRunSandboxCommandBody,
  SandboxesServiceWriteSandboxFileBody,
  V1CreateSandboxRequest,
  V1GetSandboxCommandLogsResponse,
  V1GetSandboxCommandResponse,
  V1GetSandboxFileResponse,
  V1ListSandboxesResponse,
  V1LogMessage,
  V1RunSandboxCommandResponse,
  V1Sandbox,
} from "./lightning_cloud/openapi/data-contracts.js";
import { getApiKey, getBaseUrl, mergeSandboxConfig, resolveOrgId } from "./config.js";

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
    cloudspaceId: v.cloudspaceId ?? "",
    ports: v.ports ?? [],
    runtime: v.runtime ?? "",
    createdAt: v.createdAt ?? "",
    updatedAt: v.updatedAt ?? "",
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
 * await sandbox.delete();
 * ```
 */
export class Sandbox {
  readonly sandboxId: string;
  readonly name: string;
  readonly organizationId: string;
  readonly clusterId: string;
  readonly instanceType: string;
  readonly spot: boolean;
  readonly status: string;
  readonly cloudspaceId: string;
  readonly ports: string[];
  readonly runtime: string;
  readonly createdAt: Date;
  readonly updatedAt: Date;

  private constructor(data: SandboxData) {
    this.sandboxId = data.id;
    this.name = data.name;
    this.organizationId = data.organizationId;
    this.clusterId = data.clusterId;
    this.instanceType = data.instanceType;
    this.spot = data.spot;
    this.status = data.status;
    this.cloudspaceId = data.cloudspaceId;
    this.ports = data.ports ?? [];
    this.runtime = data.runtime ?? "";
    this.createdAt = new Date(data.createdAt);
    this.updatedAt = new Date(data.updatedAt);
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
    const body: V1CreateSandboxRequest = {
      name: params.name,
      instanceType: params.instanceType,
      spot: params.spot ?? false,
      ports: (params.ports ?? []).map(String),
    };
    const orgId = resolveOrgId(params.organizationId);
    if (orgId) body.organizationId = orgId;
    if (params.clusterId) body.clusterId = params.clusterId;
    if (params.cloudspaceId) body.cloudspaceId = params.cloudspaceId;
    if (params.runtime) body.runtime = params.runtime;

    const data = await request<V1Sandbox>("POST", "/v1/core/sandboxes", body);
    let sandbox = new Sandbox(toSandboxData(data));

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
      sandbox = await Sandbox.get({
        sandboxId: sandbox.sandboxId,
        organizationId: sandbox.organizationId || undefined,
      });
    }

    return sandbox;
  }

  static async get(params: GetSandboxParams): Promise<Sandbox> {
    const orgId = resolveOrgId(params.organizationId);
    const qs = buildQuery({ organizationId: orgId });
    const data = await request<V1Sandbox>(
      "GET",
      `/v1/core/sandboxes/${encodeURIComponent(params.sandboxId)}${qs}`,
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
    const orgId = resolveOrgId(params.organizationId);
    const qs = buildQuery({
      organizationId: orgId,
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

  // ---------------------------------------------------------------------------
  // Instance methods — commands
  // ---------------------------------------------------------------------------

  async runCommand(command: string, args?: string[]): Promise<CommandResult>;
  async runCommand(opts: RunCommandOpts): Promise<CommandResult>;
  async runCommand(
    commandOrOpts: string | RunCommandOpts,
    args?: string[],
  ): Promise<CommandResult> {
    const body: SandboxesServiceRunSandboxCommandBody = {
      organizationId: this.organizationId || undefined,
    };

    if (typeof commandOrOpts === "string") {
      body.command = commandOrOpts;
      body.args = args ?? [];
    } else {
      body.command = commandOrOpts.cmd;
      body.args = commandOrOpts.args ?? [];
      if (commandOrOpts.cwd) body.cwd = commandOrOpts.cwd;
      if (commandOrOpts.env) body.env = commandOrOpts.env;
      if (commandOrOpts.sudo !== undefined) body.sudo = commandOrOpts.sudo;
      if (commandOrOpts.detached !== undefined) body.detached = commandOrOpts.detached;
    }

    const data = await request<V1RunSandboxCommandResponse>(
      "POST",
      `/v1/core/sandboxes/${encodeURIComponent(this.sandboxId)}/commands`,
      body,
    );

    return {
      cmdId: data.cmdId ?? "",
      output: data.output ?? "",
      exitCode: data.exitCode ?? 0,
    };
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
}
