import type {
  V1SandboxReadyCheck,
  V1SandboxWarmSpec,
  V1SandboxWarmStatus,
} from "./lightning_cloud/openapi/data-contracts.js";

/**
 * Warm sandbox recipes.
 *
 * A recipe says what a sandbox should already have done by the time you get it:
 * packages installed, a server listening, a runtime warmed up. Lightning runs
 * it once, snapshots the result, and restores later sandboxes with the same
 * recipe from that snapshot instead of running it again.
 *
 * The recipe *is* the cache key — there is no template id to store or refresh.
 * The key also covers the image, the sandbox shape and the host runtime
 * version, so a rebuilt image invalidates it on its own.
 *
 * ```ts
 * import { Sandbox, waitForPort } from "@lightningai/sdk";
 *
 * const sandbox = await Sandbox.create({
 *   instanceType: "cpu-2",
 *   image: "docker.io/library/python:3.13",
 *   ports: [8888],
 *   warm: {
 *     runCmd: ["pip install jupyterlab"],
 *     startCmd: "jupyter lab --ip=0.0.0.0 --port=8888",
 *     readyCmd: waitForPort(8888),
 *   },
 * });
 * sandbox.warm?.state; // "restored" | "building" | "cold"
 * ```
 *
 * The first create for a recipe is served cold with the recipe run inline, so
 * you always get the sandbox you asked for; it is only slower. Baking happens
 * in the background once a recipe has been asked for more than once, and
 * checkpoints are per host, so expect the first creates across a cluster to
 * report `cold` or `building` rather than a clean second-create hit.
 *
 * Warm only pays when the recipe is the expensive part. For a trivial recipe,
 * restoring a checkpoint costs more than the boot it replaces.
 */

/**
 * What a sandbox did about its recipe. `"unknown"` covers a state this SDK
 * build predates, so a newer backend cannot break an older client.
 */
export type WarmState = "restored" | "building" | "cold" | "unknown";

/** Where a per-sandbox value comes from. */
export type RebindSource = "generated-token" | "sandbox-id" | "hostname";

/**
 * When the recipe is finished and the sandbox is worth snapshotting. Build one
 * with {@link waitForPort} and friends rather than by hand.
 */
export type ReadyCheck =
  | { port: number }
  | { url: string; statusCode?: number }
  | { process: string }
  | { file: string }
  | { timeoutMs: number }
  | { exec: string };

/** Ready once something is listening on this TCP port inside the sandbox. */
export const waitForPort = (port: number): ReadyCheck => ({ port });

/**
 * Ready once this URL, resolved from inside the sandbox, answers.
 *
 * Defaults to expecting 200. An endpoint behind authentication answers 403
 * until you authenticate, so a port check is often the more honest signal for a
 * server that requires a token.
 */
export const waitForUrl = (url: string, statusCode?: number): ReadyCheck => ({ url, statusCode });

/** Ready once a process with this name is running. */
export const waitForProcess = (name: string): ReadyCheck => ({ process: name });

/** Ready once this path exists inside the sandbox. */
export const waitForFile = (path: string): ReadyCheck => ({ file: path });

/**
 * Ready after a fixed wait — the blunt option when nothing is observable.
 * Honoured only when no other check is set: a bare sleep must never shadow a
 * real probe.
 */
export const waitForTimeout = (milliseconds: number): ReadyCheck => ({ timeoutMs: milliseconds });

/** Ready once this shell command exits 0. */
export const waitForCommand = (command: string): ReadyCheck => ({ exec: command });

/**
 * A value that must differ per sandbox despite the shared snapshot.
 *
 * The bake runs against `bakeValue`, so a credential-bearing process starts
 * against a placeholder and no live credential is ever captured in the shared
 * snapshot. Lightning materializes the real value at restore, writes it to
 * `/run/lightning/warm/<name>`, and returns it once in
 * {@link Sandbox.warmSecrets}.
 *
 * `bakeValue` is required for `"generated-token"`: the real value cannot exist
 * until a sandbox does.
 */
export interface RebindVar {
  name: string;
  source: RebindSource;
  bakeValue?: string;
}

/**
 * What a sandbox should already have done when you get it.
 *
 * `runCmd` runs first, then `startCmd`, then — once `readyCmd` passes —
 * `afterStartCmd`. All of it happens at bake time; a restored sandbox observes
 * the effects without re-running anything.
 */
export interface WarmRecipe {
  /** Setup commands, in order. Bake-time only. */
  runCmd?: string | string[];
  /** The long-running process to leave running in the snapshot. */
  startCmd?: string;
  /**
   * Commands run once `startCmd` is up and `readyCmd` has passed — the only
   * place a recipe can warm something that does not exist until the server is
   * running, such as a Jupyter kernel. `runCmd` cannot: nothing is listening
   * when it runs.
   */
  afterStartCmd?: string | string[];
  /**
   * When to snapshot. Defaults to a TCP listen check on the first declared
   * port, or to `startCmd` exiting 0 when no ports are declared.
   */
  readyCmd?: ReadyCheck;
  /** How long to keep retrying `readyCmd`. Default two minutes. */
  readyTimeoutMs?: number;
  /**
   * Environment for the bake. Captured in the snapshot and therefore shared by
   * every sandbox restored from it: configuration only, never a credential.
   * Use `rebind` for those.
   */
  envs?: Record<string, string>;
  /** Values that must differ per sandbox. */
  rebind?: RebindVar[];
  /**
   * Command run in each restored sandbox once its rebind values are in place,
   * before it is reported ready.
   */
  afterRestoreCmd?: string;
  /** Budget for `afterRestoreCmd`. Default ten seconds. */
  afterRestoreTimeoutMs?: number;
  /**
   * Fail the create rather than serve it cold when nothing is baked. For tests
   * and benchmarks that need to assert a warm start.
   */
  requireWarm?: boolean;
  /** Ignore any existing snapshot and bake a fresh one. */
  skipCache?: boolean;
}

/**
 * Whether a sandbox restored from a baked snapshot, and if not, why.
 *
 * The failure mode of warm sandboxes is a cold start that looks exactly like a
 * warm one, so read {@link state} rather than assuming.
 */
export interface WarmStatus {
  state: WarmState;
  /**
   * Opaque digest of the recipe, image, shape and runtime version. Stable
   * across sandboxes that share a snapshot; not a handle you pass back.
   */
  templateKey: string;
  /** Why the sandbox did not restore, when it did not. */
  reason?: string;
  /** Milliseconds spent restoring, when `state` is `"restored"`. */
  restoreMs?: number;
}

const REBIND_SOURCES: Record<RebindSource, string> = {
  "generated-token": "SANDBOX_REBIND_SOURCE_GENERATED_TOKEN",
  "sandbox-id": "SANDBOX_REBIND_SOURCE_SANDBOX_ID",
  hostname: "SANDBOX_REBIND_SOURCE_HOSTNAME",
};

const WARM_STATES: Record<string, WarmState> = {
  SANDBOX_WARM_STATE_RESTORED: "restored",
  SANDBOX_WARM_STATE_BUILDING: "building",
  SANDBOX_WARM_STATE_COLD: "cold",
};

const asArray = (value: string | string[] | undefined): string[] | undefined => {
  if (value === undefined) return undefined;
  return Array.isArray(value) ? value : [value];
};

function toV1ReadyCheck(check: ReadyCheck): V1SandboxReadyCheck {
  if ("port" in check) return { port: check.port };
  if ("url" in check) return { url: { url: check.url, statusCode: check.statusCode } };
  if ("process" in check) return { process: check.process };
  if ("file" in check) return { file: check.file };
  if ("timeoutMs" in check) return { timeoutMs: check.timeoutMs };
  return { exec: check.exec };
}

/** Convert an SDK recipe into the wire shape. */
export function toV1Warm(warm: WarmRecipe | undefined): V1SandboxWarmSpec | undefined {
  if (warm === undefined) return undefined;

  const runCmd = asArray(warm.runCmd);
  const afterStartCmd = asArray(warm.afterStartCmd);
  if (!runCmd?.length && !warm.startCmd) {
    throw new Error("warm needs at least one runCmd or a startCmd.");
  }
  if (afterStartCmd?.length && !warm.startCmd) {
    throw new Error("warm.afterStartCmd needs a startCmd: it runs once that process is up.");
  }

  return {
    runCmd,
    startCmd: warm.startCmd,
    afterStartCmd,
    readyCmd: warm.readyCmd ? toV1ReadyCheck(warm.readyCmd) : undefined,
    readyTimeoutMs: warm.readyTimeoutMs,
    envs: warm.envs,
    rebind: warm.rebind?.map((v) => ({
      name: v.name,
      source: REBIND_SOURCES[v.source],
      bakeValue: v.bakeValue,
    })),
    afterRestoreCmd: warm.afterRestoreCmd,
    afterRestoreTimeoutMs: warm.afterRestoreTimeoutMs,
    requireWarm: warm.requireWarm,
    skipCache: warm.skipCache,
  } as V1SandboxWarmSpec;
}

/**
 * Convert a backend status, mapping the wire enum to a short state.
 *
 * An unrecognised state becomes `"unknown"` rather than leaking a wire value
 * like `"SANDBOX_WARM_STATE_…"` into comparisons that would silently never
 * match.
 */
export function fromV1WarmStatus(status: V1SandboxWarmStatus | undefined): WarmStatus | undefined {
  if (!status) return undefined;
  return {
    state: WARM_STATES[String((status as { state?: string }).state ?? "")] ?? "unknown",
    templateKey: (status as { templateKey?: string }).templateKey ?? "",
    reason: (status as { reason?: string }).reason,
    restoreMs: (status as { restoreMs?: number }).restoreMs,
  };
}
