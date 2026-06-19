"""Sandbox egress firewall policy (maps to ``V1NetworkPolicy``).

A single :class:`NetworkPolicy` models every egress mode (mirrors Vercel's
``NetworkPolicy``):

  - ``NetworkPolicy("allow-all")`` — open egress (the default)
  - ``NetworkPolicy("deny-all")`` — block all egress
  - ``NetworkPolicy(allow_cidrs=[...])`` — CIDR allowlist (``default-deny`` for
    everything else)

For convenience, :meth:`~lightning_sdk.sandbox.sandbox.Sandbox.create` also
accepts the bare ``"allow-all"`` / ``"deny-all"`` strings. Policies are set at
create time only; restored snapshots inherit the source policy unless
overridden. Reading :attr:`~lightning_sdk.sandbox.base.SandboxInstance.network_policy`
always returns a :class:`NetworkPolicy`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from lightning_sdk.lightning_cloud.openapi.models import V1NetworkPolicy

NetworkPolicyMode: TypeAlias = Literal["allow-all", "deny-all", "default-deny"]
#: Bare-string shorthands accepted at create time.
NetworkPolicyShorthand: TypeAlias = Literal["allow-all", "deny-all"]


@dataclass(frozen=True)
class NetworkPolicy:
    """Sandbox egress firewall policy.

    ``mode`` is one of ``"allow-all"`` (open egress), ``"deny-all"`` (block all),
    or ``"default-deny"`` (deny everything except ``allow_cidrs``). Passing
    ``allow_cidrs`` without an explicit ``mode`` implies ``"default-deny"``.
    """

    mode: NetworkPolicyMode = "allow-all"
    allow_cidrs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Infer ``default-deny`` when CIDRs are supplied without an explicit mode."""
        if self.allow_cidrs and self.mode == "allow-all":
            object.__setattr__(self, "mode", "default-deny")

    def to_v1(self) -> V1NetworkPolicy:
        return V1NetworkPolicy(
            mode=self.mode,
            allowed_cidrs=list(self.allow_cidrs),
        )


NetworkPolicyInput: TypeAlias = NetworkPolicyShorthand | NetworkPolicy | V1NetworkPolicy | None


def to_v1_network_policy(
    policy: NetworkPolicyInput,
) -> V1NetworkPolicy | None:
    """Convert SDK policy values (or pass through ``V1NetworkPolicy``)."""
    if policy is None:
        return None
    if isinstance(policy, V1NetworkPolicy):
        return policy
    if isinstance(policy, str):
        return V1NetworkPolicy(mode=policy)
    if isinstance(policy, NetworkPolicy):
        return policy.to_v1()
    raise TypeError(
        f"network_policy must be 'allow-all', 'deny-all', NetworkPolicy, or V1NetworkPolicy, got {type(policy)!r}",
    )


def from_v1_network_policy(
    policy: V1NetworkPolicy | None,
) -> NetworkPolicy:
    """Convert a backend ``V1NetworkPolicy`` into a :class:`NetworkPolicy`.

    Inverse of :func:`to_v1_network_policy`. Open egress (no policy stored) and
    an explicit ``allow-all`` both normalize to ``NetworkPolicy("allow-all")``,
    matching the create-time default, so callers always get a single type and
    never see ``None`` or the generated ``V1NetworkPolicy``.
    """
    if policy is None:
        return NetworkPolicy(mode="allow-all")
    mode = getattr(policy, "mode", None) or "allow-all"
    cidrs = list(getattr(policy, "allowed_cidrs", None) or [])
    if mode not in ("allow-all", "deny-all", "default-deny"):
        mode = "default-deny" if cidrs else "allow-all"
    return NetworkPolicy(mode=mode, allow_cidrs=cidrs)
