from __future__ import annotations

from unittest import mock

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
    api = SandboxConfig(api_key="k", base_url="https://x", organization_id="org-uuid").api()
    assert api.config_get("api_key") == "k"
    assert api.config_get("base_url") == "https://x"
    assert api.config_get("organization_id") == "org-uuid"


def test_sandbox_config_api_without_organization_id():
    api = SandboxConfig(api_key="k", base_url="https://x").api()
    assert api.config_get("organization_id") is None
