from __future__ import annotations

from lightning_sdk.lightning_cloud.openapi import V1NetworkPolicy
from lightning_sdk.lightning_cloud.openapi.api_client import ApiClient
from lightning_sdk.lightning_cloud.openapi.models import V1CreateSandboxRequest
from lightning_sdk.sandbox.network_policy import NetworkPolicy, to_v1_network_policy


def test_network_policy_to_v1():
    policy = NetworkPolicy(allow_cidrs=["1.1.1.1/32", "10.0.1.10/32"])
    v1 = policy.to_v1()
    assert v1.mode == "default-deny"
    assert v1.allowed_cidrs == ["1.1.1.1/32", "10.0.1.10/32"]


def test_to_v1_network_policy_from_dataclass():
    v1 = to_v1_network_policy(NetworkPolicy(allow_cidrs=["1.1.1.1/32"]))
    assert v1 is not None
    assert v1.mode == "default-deny"
    assert v1.allowed_cidrs == ["1.1.1.1/32"]


def test_network_policy_string_literals():
    assert to_v1_network_policy("allow-all").mode == "allow-all"
    assert to_v1_network_policy("deny-all").mode == "deny-all"


def test_network_policy_omit_is_none():
    assert to_v1_network_policy(None) is None


def test_to_v1_network_policy_pass_through():
    v1 = V1NetworkPolicy(mode="allow-all")
    assert to_v1_network_policy(v1) is v1


def test_create_request_serializes_network_policy_camel_case():
    body = V1CreateSandboxRequest(
        name="x",
        instance_type="cpu-2",
        network_policy=V1NetworkPolicy(mode="deny-all"),
    )
    payload = ApiClient().sanitize_for_serialization(body)
    assert payload["networkPolicy"] == {"mode": "deny-all"}
