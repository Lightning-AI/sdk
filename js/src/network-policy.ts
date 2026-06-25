import type { V1NetworkPolicy } from "./lightning_cloud/openapi/data-contracts.js";

/**
 * Egress policy mode. Mirrors the Python SDK's `NetworkPolicy`:
 *
 * - `"allow-all"` — open egress (the default)
 * - `"deny-all"` — block all egress
 * - `"default-deny"` — deny everything except {@link NetworkPolicy.allowCidrs}
 */
export type NetworkPolicyMode = "allow-all" | "deny-all" | "default-deny";

/** Bare-string shorthands accepted at create time. */
export type NetworkPolicyShorthand = "allow-all" | "deny-all";

/** Anything {@link Sandbox.create} accepts for `networkPolicy`. */
export type NetworkPolicyInput =
  | NetworkPolicyShorthand
  | NetworkPolicy
  | V1NetworkPolicy;

/**
 * Sandbox egress firewall policy, set at create time only (no runtime
 * mutation). A single `NetworkPolicy` models every mode:
 *
 * ```ts
 * import { NetworkPolicy, Sandbox } from "@lightning-ai/sandbox";
 *
 * const locked = await Sandbox.create({
 *   name: "egress-test",
 *   instanceType: "cpu-1",
 *   networkPolicy: new NetworkPolicy({ allowCidrs: ["10.0.0.0/8"] }),
 * });
 * console.log(locked.networkPolicy.mode); // "default-deny"
 * ```
 *
 * Passing `allowCidrs` without an explicit `mode` implies `"default-deny"`.
 */
export class NetworkPolicy {
  readonly mode: NetworkPolicyMode;
  readonly allowCidrs: string[];

  constructor(opts: { mode?: NetworkPolicyMode; allowCidrs?: string[] } = {}) {
    const allowCidrs = opts.allowCidrs ?? [];
    let mode = opts.mode ?? "allow-all";
    // Infer default-deny when CIDRs are supplied without an explicit mode.
    if (allowCidrs.length > 0 && mode === "allow-all") {
      mode = "default-deny";
    }
    this.mode = mode;
    this.allowCidrs = allowCidrs;
  }

  toV1(): V1NetworkPolicy {
    return { mode: this.mode, allowedCidrs: [...this.allowCidrs] };
  }
}

/** Convert SDK policy values (or pass through a raw `V1NetworkPolicy`). */
export function toV1NetworkPolicy(
  policy: NetworkPolicyInput | undefined,
): V1NetworkPolicy | undefined {
  if (policy === undefined) return undefined;
  if (typeof policy === "string") return { mode: policy };
  if (policy instanceof NetworkPolicy) return policy.toV1();
  return policy;
}

/**
 * Convert a backend `V1NetworkPolicy` into a {@link NetworkPolicy}. Open egress
 * (no stored policy) and an explicit `allow-all` both normalize to
 * `new NetworkPolicy({ mode: "allow-all" })`, so callers never get `undefined`
 * or a raw `V1NetworkPolicy` back.
 */
export function fromV1NetworkPolicy(
  policy: V1NetworkPolicy | undefined,
): NetworkPolicy {
  if (!policy) return new NetworkPolicy({ mode: "allow-all" });
  const cidrs = policy.allowedCidrs ?? [];
  let mode = policy.mode ?? "allow-all";
  if (mode !== "allow-all" && mode !== "deny-all" && mode !== "default-deny") {
    mode = cidrs.length > 0 ? "default-deny" : "allow-all";
  }
  return new NetworkPolicy({ mode: mode as NetworkPolicyMode, allowCidrs: cidrs });
}
