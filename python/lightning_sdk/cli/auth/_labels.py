"""User-facing labels for RBAC roles and permissions.

Ported from the web UI's single source of truth (grid ``lightning-ui``
``src/utils/roles.ts``). Keep roughly in sync with it; the proto enums
(``V1RuleResource`` / ``V1RuleAction`` / ``V1RuleEffect``) are the shared contract.
"""

import re
from typing import Optional

from lightning_sdk.lightning_cloud.openapi import V1RuleAction, V1RuleResource

# Sentinel enum values that carry no meaning for a user; hidden from output.
_HIDDEN_ACTIONS = {V1RuleAction.UNSPECIFIEDACTION}
_HIDDEN_RESOURCES = {V1RuleResource.UNSPECIFIEDRESOURCE}

_RESOURCE_LABELS = {
    "project": "Teamspaces",
    "cloudSpace": "Studios",
    "multiMachineJob": "Multi-machine training (MMT)",
    "litLogger": "Experiments",
    "managedEndpoint": "Managed Services",
    "dataConnection": "Storage",
    "kubernetesCluster": "Compute",
    "cluster": "Connected Clusters",
    "assistant": "AI copilot",
    "orgBilling": "Billing",
    "sshKey": "SSH keys",
    "orgRole": "Organization Roles",
    "orgMembership": "Organization membership",
}

_ACTION_LABELS = {
    "ssh": "SSH",
    "viewLogs": "View logs",
    "getNotified": "Get notified",
}

_EFFECT_LABELS = {
    "allow": "Allow",
    "deny": "Deny",
}


def _camel_case_to_label(value: str) -> str:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return spaced[:1].upper() + spaced[1:]


def is_visible_action(action: str) -> bool:
    """Whether an action is meaningful enough to show a user."""
    return action not in _HIDDEN_ACTIONS


def is_visible_resource(resource: str) -> bool:
    """Whether a resource is meaningful enough to show a user."""
    return resource not in _HIDDEN_RESOURCES


def resource_label(resource: str) -> str:
    """Return the user-facing label for a permission resource."""
    return _RESOURCE_LABELS.get(resource) or _camel_case_to_label(resource)


def action_label(action: str) -> str:
    """Return the user-facing label for a permission action."""
    return _ACTION_LABELS.get(action) or _camel_case_to_label(action)


def effect_label(effect: str) -> str:
    """Return the user-facing label for a rule effect."""
    return _EFFECT_LABELS.get(effect) or _camel_case_to_label(effect)


def condition_label(condition: object) -> Optional[str]:
    """Summarize a rule condition, or None when there is no condition."""
    if condition is None:
        return None
    parts = []
    if getattr(condition, "resource_owner", None):
        parts.append("own resources only")
    if resource_id := getattr(condition, "resource_id", None):
        parts.append(f"resource {resource_id}")
    if cloudspace_id := getattr(condition, "cloudspace_id", None):
        parts.append(f"studio {cloudspace_id}")
    if project_id := getattr(condition, "project_id", None):
        parts.append(f"teamspace {project_id}")
    return ", ".join(parts) or None
