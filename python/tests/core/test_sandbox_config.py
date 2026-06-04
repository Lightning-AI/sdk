from __future__ import annotations

import pytest

from lightning_sdk.sandbox.config import SandboxConfig


def test_sandbox_config_to_api_dict_includes_organization_id():
    cfg = SandboxConfig(api_key="k", base_url="https://x", organization_id="org-uuid")
    assert cfg.to_api_dict() == {
        "api_key": "k",
        "base_url": "https://x",
        "organization_id": "org-uuid",
    }


def test_sandbox_config_to_api_dict_omits_organization_id_when_unset():
    cfg = SandboxConfig(api_key="k", base_url="https://x")
    assert cfg.to_api_dict() == {"api_key": "k", "base_url": "https://x"}
    assert "organization_id" not in cfg.to_api_dict()


def test_sandbox_config_api_requires_api_key():
    with pytest.raises(ValueError, match="api_key is required"):
        SandboxConfig(base_url="https://x").api()


def test_sandbox_config_api_passes_through_config():
    api = SandboxConfig(api_key="k", base_url="https://x", organization_id="org-uuid").api()
    assert api.config_get("api_key") == "k"
    assert api.config_get("base_url") == "https://x"
    assert api.config_get("organization_id") == "org-uuid"


def test_sandbox_config_api_without_organization_id():
    api = SandboxConfig(api_key="k", base_url="https://x").api()
    assert api.config_get("organization_id") is None
