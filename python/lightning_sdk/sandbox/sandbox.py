from __future__ import annotations

from typing import Any, Callable

from lightning_sdk.api.sandbox_api import SandboxApi
from lightning_sdk.sandbox.base import (
    ListSandboxesResult,
    SandboxInstance,
    create_sandbox,
)
from lightning_sdk.sandbox.config import SandboxConfig


def _sandbox_create_impl(
    *,
    sandbox_api: SandboxApi | None = None,
    config: SandboxConfig | None = None,
    name: str | None = None,
    instance_type: str | None = None,
    runtime: str | None = None,
    spot: bool = False,
    ports: list[int | str] | None = None,
    organization_id: str | None = None,
    cluster_id: str | None = None,
    cloudspace_id: str | None = None,
) -> SandboxInstance:
    if sandbox_api is not None and config is not None:
        raise ValueError("Pass only one of 'config' and sandbox_api (internal)")
    api = sandbox_api if sandbox_api is not None else (config if config is not None else SandboxConfig.from_env()).api()
    return create_sandbox(
        name=name,
        instance_type=instance_type,
        runtime=runtime,
        spot=spot,
        ports=ports,
        organization_id=organization_id,
        cluster_id=cluster_id,
        cloudspace_id=cloudspace_id,
        sandbox_api=api,
    )


class _SandboxCreate:
    """``Sandbox.create`` / ``Sandbox(...).create`` — see :class:`Sandbox`."""

    def __get__(self, obj: Sandbox | None, objtype: type[Sandbox] | None) -> Callable[..., SandboxInstance]:
        def bound(**kwargs: Any) -> SandboxInstance:
            if obj is None:
                return _sandbox_create_impl(**kwargs)
            if kwargs.pop("config", None) is not None:
                raise ValueError(
                    "Do not pass config= when calling create() on a Sandbox client instance; "
                    "use Sandbox.create(config=...) instead.",
                )
            if kwargs.pop("sandbox_api", None) is not None:
                raise ValueError(
                    "Do not pass sandbox_api= when calling create() on a Sandbox client instance.",
                )
            return _sandbox_create_impl(sandbox_api=obj._api, **kwargs)

        return bound


class Sandbox:
    """Sandbox API client.

    Use :meth:`create` like ``Sandbox.create(...)`` (recommended, mirrors other SDKs) or
    ``Sandbox(...).create(...)`` with that instance credentials.

    :meth:`create` accepts ``config`` for API credentials (otherwise env defaults), plus ``name``, ``instance_type``,
    ``runtime``, ``spot``, ``ports``, ``organization_id``, ``cluster_id``, and ``cloudspace_id``.

    Use :meth:`get` and :meth:`list` to obtain :class:`~lightning_sdk.sandbox.base.SandboxInstance` values.
    """

    create = _SandboxCreate()

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
