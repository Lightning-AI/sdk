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


@dataclass
class SandboxConfig:
    """Explicit sandbox API settings.

    ``api_key`` is required. ``organization_id`` is optional — set via
    ``LIGHTNING_ORG_ID`` or :attr:`organization_id`; when omitted, requests rely
    on org scope implied by the API key alone.

    Maps to environment variables used by :meth:`from_env`:

    - ``LIGHTNING_SANDBOX_API_KEY`` → ``api_key`` (required)
    - ``LIGHTNING_CLOUD_URL`` → ``base_url``
    - ``LIGHTNING_ORG_ID`` → ``organization_id`` (optional)
    """

    api_key: str | None = None
    base_url: str | None = None
    organization_id: str | None = None

    @classmethod
    def from_env(cls) -> SandboxConfig:
        """Load settings from the standard environment variables."""
        return cls(
            api_key=os.getenv(_ENV_API_KEY),
            base_url=os.getenv(_ENV_CLOUD_URL),
            organization_id=os.getenv(_ENV_ORG_ID),
        )

    def merge(self, other: SandboxConfig) -> SandboxConfig:
        """Return a new config with non-None values from *other* overriding self."""
        return SandboxConfig(
            api_key=other.api_key if other.api_key is not None else self.api_key,
            base_url=other.base_url if other.base_url is not None else self.base_url,
            organization_id=other.organization_id if other.organization_id is not None else self.organization_id,
        )

    def api(self) -> SandboxApi:
        """Build an isolated :class:`~lightning_sdk.api.sandbox_api.SandboxApi` for this config."""
        if not self.api_key:
            raise ValueError(
                "api_key is required. Set LIGHTNING_SANDBOX_API_KEY or pass api_key in SandboxConfig.",
            )
        from lightning_sdk.api.sandbox_api import SandboxApi

        return SandboxApi(self.to_api_dict())

    def to_api_dict(self) -> dict[str, Any]:
        """Shape expected by :class:`~lightning_sdk.api.sandbox_api.SandboxApi`."""
        out: dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.base_url.rstrip("/") if self.base_url else None,
        }
        if self.organization_id is not None:
            out["organization_id"] = self.organization_id
        return out
