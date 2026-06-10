"""Create-time sandbox egress policy (maps to ``V1NetworkPolicy``).

Modes:
  - omit / ``"allow-all"`` — open egress (no datapath rules)
  - ``"deny-all"`` — block all egress
  - :class:`NetworkPolicy` — CIDR allowlist (``default-deny`` for everything else)

Policies are set at :meth:`~lightning_sdk.sandbox.sandbox.Sandbox.create` only.
Restored snapshots inherit the source sandbox policy unless overridden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from lightning_sdk.lightning_cloud.openapi.models import V1NetworkPolicy


@dataclass(frozen=True)
class NetworkPolicy:
    """CIDR egress allowlist. All other traffic is denied (``default-deny``)."""

    allow_cidrs: list[str]

    def to_v1(self) -> V1NetworkPolicy:
        return V1NetworkPolicy(
            mode="default-deny",
            allowed_cidrs=list(self.allow_cidrs),
        )


NetworkPolicyMode: TypeAlias = Literal["allow-all", "deny-all"]
NetworkPolicyInput: TypeAlias = NetworkPolicyMode | NetworkPolicy | V1NetworkPolicy | None


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
