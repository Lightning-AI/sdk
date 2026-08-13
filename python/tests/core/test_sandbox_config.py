from __future__ import annotations

from unittest import mock

import pytest

from lightning_sdk.sandbox.config import SandboxConfig, reject_legacy_org_id_config


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_sandbox_config_to_api_dict():
    cfg = SandboxConfig(api_key="k", base_url="https://x")
    assert cfg.to_api_dict() == {"api_key": "k", "base_url": "https://x"}


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_sandbox_config_rejects_organization_id_kwarg():
    with pytest.raises(TypeError):
        SandboxConfig(api_key="k", organization_id="org-uuid")  # type: ignore[call-arg]


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_from_env_rejects_lightning_org_id(monkeypatch):
    monkeypatch.setenv("LIGHTNING_ORG_ID", "org-1")
    with pytest.raises(ValueError, match="LIGHTNING_ORG_ID is no longer supported"):
        SandboxConfig.from_env()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_configure_rejects_organization_id_kwarg():
    from lightning_sdk.sandbox.base import configure

    with pytest.raises(TypeError):
        configure(organization_id="org-1")  # type: ignore[call-arg]


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_sandbox_config_api_without_api_key_uses_lightning_auth():
    with mock.patch("lightning_sdk.api.sandbox_api.Auth") as auth_cls:
        auth_cls.return_value.authenticate.return_value = "Basic auth"
        api = SandboxConfig(base_url="https://x").api()
        auth_cls.return_value.authenticate.assert_not_called()
        api.sandboxes()

    assert api.config_get("api_key") is None
    assert api.config_get("base_url") == "https://x"
    auth_cls.return_value.authenticate.assert_called_once()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_sandbox_config_api_passes_through_config():
    api = SandboxConfig(api_key="k", base_url="https://x").api()
    assert api.config_get("api_key") == "k"
    assert api.config_get("base_url") == "https://x"
    assert api.config_get("organization_id") is None


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_reject_legacy_org_id_config_is_noop_without_env():
    reject_legacy_org_id_config()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_importing_sandbox_module_tolerates_legacy_org_id_env(monkeypatch):
    """Importing must not read the environment. LIGHTNING_ORG_ID is rejected, so reading
    it at import time made every `lightning` CLI command fail in an environment that
    sets it (a Lightning job does), because the CLI imports this module to register the
    sandbox command group."""
    monkeypatch.setenv("LIGHTNING_ORG_ID", "org-legacy")
    import importlib

    import lightning_sdk.sandbox.base as base

    importlib.reload(base)  # stands in for a fresh interpreter importing the module

    # ... but the rejection must still reach anyone actually reaching for a sandbox.
    with pytest.raises(ValueError, match="LIGHTNING_ORG_ID is no longer supported"):
        base._default_api()


@mock.patch("lightning_sdk.lightning_cloud.rest_client.Auth", new=mock.MagicMock())
def test_global_config_loads_env_on_first_use(monkeypatch):
    monkeypatch.setenv("LIGHTNING_SANDBOX_API_KEY", "key-from-env")
    monkeypatch.setenv("LIGHTNING_CLOUD_URL", "https://env.unit")
    import importlib

    import lightning_sdk.sandbox.base as base

    importlib.reload(base)

    assert base._global_config().api_key == "key-from-env"
    assert base._global_config().base_url == "https://env.unit"
