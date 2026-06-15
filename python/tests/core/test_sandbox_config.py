from __future__ import annotations

from unittest import mock

import pytest

from lightning_sdk.sandbox.config import SandboxConfig, reject_legacy_org_id_config


def test_sandbox_config_to_api_dict():
    cfg = SandboxConfig(api_key="k", base_url="https://x")
    assert cfg.to_api_dict() == {"api_key": "k", "base_url": "https://x"}


def test_sandbox_config_rejects_organization_id_kwarg():
    with pytest.raises(TypeError):
        SandboxConfig(api_key="k", organization_id="org-uuid")  # type: ignore[call-arg]


def test_from_env_rejects_lightning_org_id(monkeypatch):
    monkeypatch.setenv("LIGHTNING_ORG_ID", "org-1")
    with pytest.raises(ValueError, match="LIGHTNING_ORG_ID is no longer supported"):
        SandboxConfig.from_env()


def test_configure_rejects_organization_id_kwarg():
    from lightning_sdk.sandbox.base import configure

    with pytest.raises(TypeError):
        configure(organization_id="org-1")  # type: ignore[call-arg]


def test_sandbox_config_api_without_api_key_uses_lightning_auth():
    with mock.patch("lightning_sdk.api.sandbox_api.Auth") as auth_cls:
        auth_cls.return_value.authenticate.return_value = "Basic auth"
        api = SandboxConfig(base_url="https://x").api()
        auth_cls.return_value.authenticate.assert_not_called()
        api.sandboxes()

    assert api.config_get("api_key") is None
    assert api.config_get("base_url") == "https://x"
    auth_cls.return_value.authenticate.assert_called_once()


def test_sandbox_config_api_passes_through_config():
    api = SandboxConfig(api_key="k", base_url="https://x").api()
    assert api.config_get("api_key") == "k"
    assert api.config_get("base_url") == "https://x"
    assert api.config_get("organization_id") is None


def test_reject_legacy_org_id_config_is_noop_without_env():
    reject_legacy_org_id_config()
