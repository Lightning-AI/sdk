import type { SandboxConfig } from "./types.js";

/** Default Lightning Cloud origin when no base URL is configured. */
export const DEFAULT_LIGHTNING_BASE_URL = "https://lightning.ai";

let globalConfig: SandboxConfig = {};

/**
 * Merges options into the SDK-wide defaults used by HTTP requests.
 * Called by {@link Sandbox.configure}; prefer that on the public API.
 */
export function mergeSandboxConfig(patch: SandboxConfig): void {
  globalConfig = { ...globalConfig, ...patch };
}

/** Clears module-level config (for tests and process isolation). Not exported from the package root. */
export function resetSandboxConfig(): void {
  globalConfig = {};
}

export function getApiKey(override?: string): string {
  const env =
    typeof process !== "undefined"
      ? (process.env.LIGHTNING_SANDBOX_API_KEY ?? process.env.LIGHTNING_API_KEY)
      : undefined;
  const key = override ?? globalConfig.apiKey ?? env;
  if (!key) {
    throw new Error(
      "Missing API key. Pass apiKey to Sandbox.configure(), provide it in create/get options, or set the LIGHTNING_SANDBOX_API_KEY environment variable.",
    );
  }
  return key;
}

export function getBaseUrl(): string {
  return (
    globalConfig.baseUrl ??
    (typeof process !== "undefined" ? process.env.LIGHTNING_CLOUD_URL : undefined) ??
    DEFAULT_LIGHTNING_BASE_URL
  );
}
