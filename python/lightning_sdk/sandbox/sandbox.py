from __future__ import annotations

from lightning_sdk.api.sandbox_api import SandboxApi
from lightning_sdk.sandbox.base import (
    ListSandboxesResult,
    SandboxInstance,
    create_sandbox,
)
from lightning_sdk.sandbox.config import SandboxConfig


class Sandbox:
    """Entry point with isolated credentials: ``sdk = Sandbox()`` or ``sdk = Sandbox(SandboxConfig(...))``.

    Use :meth:`create`, :meth:`get`, and :meth:`list` to obtain :class:`~lightning_sdk.sandbox.base.SandboxInstance`
    objects.
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config if config is not None else SandboxConfig.from_env()
        self._api = self._config.api()

    @property
    def config(self) -> SandboxConfig:
        return self._config

    @property
    def api(self) -> SandboxApi:
        return self._api

    @classmethod
    def configure(
        cls,
        config: SandboxConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        organization_id: str | None = None,
    ) -> None:
        SandboxInstance.configure(
            config=config,
            api_key=api_key,
            base_url=base_url,
            organization_id=organization_id,
        )

    def create(
        self,
        *,
        name: str | None = None,
        instance_type: str | None = None,
        runtime: str | None = None,
        spot: bool = False,
        ports: list[int | str] | None = None,
        organization_id: str | None = None,
        cluster_id: str | None = None,
        cloudspace_id: str | None = None,
    ) -> SandboxInstance:
        return create_sandbox(
            name=name,
            instance_type=instance_type,
            runtime=runtime,
            spot=spot,
            ports=ports,
            organization_id=organization_id,
            cluster_id=cluster_id,
            cloudspace_id=cloudspace_id,
            sandbox_api=self._api,
        )

    def get(
        self,
        sandbox_id: str,
        *,
        organization_id: str | None = None,
    ) -> SandboxInstance:
        return SandboxInstance.get(sandbox_id, organization_id=organization_id, sandbox_api=self._api)

    def list(
        self,
        *,
        organization_id: str | None = None,
        page_token: str | None = None,
        limit: int | None = None,
    ) -> ListSandboxesResult:
        return SandboxInstance.list(
            organization_id=organization_id,
            page_token=page_token,
            limit=limit,
            sandbox_api=self._api,
        )
