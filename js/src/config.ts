import type { SandboxConfig } from "./types.js";

/** Default Lightning Cloud origin when no base URL is configured. */
export const DEFAULT_LIGHTNING_BASE_URL = "https://platform.lightning.ai";

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

const LEGACY_API_KEY_MESSAGE =
  "LIGHTNING_API_KEY holds a legacy API key, which is no longer supported. Create a service-account key (lit_sa_) and set LIGHTNING_API_KEY to it. If you are on an older @lightning-ai/sdk, upgrade it.";
const LEGACY_UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Reads LIGHTNING_API_KEY, refusing the legacy user (UUID) and org (sk-lit-) key formats. */
function legacyEnvApiKey(): string | undefined {
  const key = process.env.LIGHTNING_API_KEY;
  if (key && (key.startsWith("sk-lit-") || LEGACY_UUID_PATTERN.test(key))) {
    throw new Error(LEGACY_API_KEY_MESSAGE);
  }
  return key;
}

function sandboxEnvApiKey(): string | undefined {
  if (typeof process === "undefined") {
    return undefined;
  }
  return process.env.LIGHTNING_SANDBOX_API_KEY ?? legacyEnvApiKey();
}

export function getApiKey(override?: string): string {
  const key = override ?? globalConfig.apiKey ?? sandboxEnvApiKey();
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
