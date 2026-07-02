"""Sandbox SDK configuration (explicit + environment variables)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lightning_sdk.api.sandbox_api import SandboxApi

_ENV_API_KEY = "LIGHTNING_SANDBOX_API_KEY"
_ENV_CLOUD_URL = "LIGHTNING_CLOUD_URL"
_ENV_ORG_ID = "LIGHTNING_ORG_ID"

ORG_ID_NOT_SUPPORTED_MSG = (
    "organization_id is not supported in SandboxConfig. "
    "Org scope is determined by your API key. "
    "Use a teamspace-scoped key from Lightning (Members → API keys)."
)


def reject_legacy_org_id_config() -> None:
    """Raise if ``LIGHTNING_ORG_ID`` is set (org scope comes from the API key)."""
    if os.getenv(_ENV_ORG_ID):
        raise ValueError(f"LIGHTNING_ORG_ID is no longer supported. {ORG_ID_NOT_SUPPORTED_MSG}")


@dataclass
class SandboxConfig:
    """Explicit sandbox API settings.

    ``api_key`` is optional. When omitted, the sandbox client falls back to the
    credentials from ``lightning login`` / standard Lightning auth env vars.
    Organization scope is implied by the API key — do not pass ``organization_id``.

    Maps to environment variables used by :meth:`from_env`:

    - ``LIGHTNING_SANDBOX_API_KEY`` → ``api_key``
    - ``LIGHTNING_CLOUD_URL`` → ``base_url``
    """

    api_key: str | None = None
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> SandboxConfig:
        """Load settings from the standard environment variables."""
        reject_legacy_org_id_config()
        return cls(
            api_key=os.getenv(_ENV_API_KEY),
            base_url=os.getenv(_ENV_CLOUD_URL),
        )

    def merge(self, other: SandboxConfig) -> SandboxConfig:
        """Return a new config with non-None values from *other* overriding self."""
        return SandboxConfig(
            api_key=other.api_key if other.api_key is not None else self.api_key,
            base_url=other.base_url if other.base_url is not None else self.base_url,
        )

    def api(self) -> SandboxApi:
        """Build an isolated :class:`~lightning_sdk.api.sandbox_api.SandboxApi` for this config."""
        from lightning_sdk.api.sandbox_api import SandboxApi

        return SandboxApi(self.to_api_dict())

    def to_api_dict(self) -> dict[str, Any]:
        """Shape expected by :class:`~lightning_sdk.api.sandbox_api.SandboxApi`."""
        return {
            "api_key": self.api_key,
            "base_url": self.base_url.rstrip("/") if self.base_url else None,
        }
