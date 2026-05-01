from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lightning_sdk.lightning_cloud import env as lightning_env
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import SandboxesServiceApi
from lightning_sdk.lightning_cloud.openapi.models import (
    SandboxesServiceCreateSandboxDirectoryBody,
    SandboxesServiceRunSandboxCommandBody,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient


@dataclass
class CommandStatus:
    output: str
    exit_code: int


@dataclass
class CommandResult:
    cmd_id: str
    output: str
    exit_code: int

    def stdout(self) -> str:
        """Combined stdout/stderr for this command (same as ``output``)."""
        return self.output


@dataclass
class CommandLog:
    timestamp: str
    message: str


def _api_exception_text(exc: ApiException) -> str:
    body = getattr(exc, "body", None)
    if body:
        try:
            return body.decode() if isinstance(body, (bytes, bytearray)) else str(body)
        except Exception:
            return str(body)
    return str(exc.reason or exc)


def _parse_run_command_response(resp: Any) -> CommandResult:
    if resp is None:
        return CommandResult(cmd_id="", output="", exit_code=0)
    d = resp.to_dict() if hasattr(resp, "to_dict") else {}
    return CommandResult(
        cmd_id=str(d.get("cmd_id") or ""),
        output=str(d.get("output") or ""),
        exit_code=int(d.get("exit_code") or 0),
    )


def _parse_get_command_response(resp: Any) -> CommandStatus:
    if resp is None:
        return CommandStatus(output="", exit_code=0)
    d = resp.to_dict() if hasattr(resp, "to_dict") else {}
    return CommandStatus(
        output=str(d.get("output") or ""),
        exit_code=int(d.get("exit_code") or 0),
    )


def _parse_command_logs_response(resp: Any) -> list[CommandLog]:
    if resp is None:
        return []
    logs_attr = getattr(resp, "logs", None)
    if not logs_attr:
        return []
    return [
        CommandLog(
            timestamp=str(x.timestamp if hasattr(x, "timestamp") else ""),
            message=str(x.message if hasattr(x, "message") else ""),
        )
        for x in logs_attr
    ]


class SandboxApi:
    """Internal API client for Core sandbox requests (generated OpenAPI)."""

    @staticmethod
    def _create_run_sandbox_command_body(
        *,
        command: str,
        args: list[str] | None = None,
        organization_id: str | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        sudo: bool | None = None,
        detached: bool | None = None,
    ) -> SandboxesServiceRunSandboxCommandBody:
        """Build the request body for :meth:`run_command`."""
        body = SandboxesServiceRunSandboxCommandBody(command=command)
        if args is not None:
            body.args = args
        if organization_id is not None:
            body.organization_id = organization_id
        if cwd is not None:
            body.cwd = cwd
        if env is not None:
            body.env = env
        if sudo is not None:
            body.sudo = sudo
        if detached is not None:
            body.detached = detached
        return body

    @staticmethod
    def _create_sandbox_directory_body(
        *,
        path: str,
        organization_id: str | None = None,
    ) -> SandboxesServiceCreateSandboxDirectoryBody:
        """Build the request body for :meth:`create_directory`."""
        body = SandboxesServiceCreateSandboxDirectoryBody(path=path)
        if organization_id is not None:
            body.organization_id = organization_id
        return body

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._client = LightningClient(max_tries=7)
        self._apply_auth_and_host()

    def config_get(self, key: str) -> Any:
        return self._config.get(key)

    def reset(self) -> None:
        """Recreate the Lightning client and re-apply ``configure()`` / env (call after config changes)."""
        self._client = LightningClient(max_tries=7)
        self._apply_auth_and_host()

    invalidate = reset

    def _apply_auth_and_host(self) -> None:
        host = str(self._config.get("base_url") or lightning_env.LIGHTNING_CLOUD_URL).rstrip("/")
        self._client.api_client.configuration.host = host
        if self._config.get("api_key"):
            self._client.api_client.set_default_header("Authorization", f"Bearer {self._config['api_key']}")
        else:
            auth_header = Auth().authenticate()
            if not auth_header:
                raise RuntimeError(
                    "Missing credentials: set api_key via configure() or use lightning login / env vars."
                )
            self._client.api_client.set_default_header("Authorization", auth_header)

    @property
    def client(self) -> LightningClient:
        return self._client

    @property
    def host(self) -> str:
        return str(self._client.api_client.configuration.host).rstrip("/")

    def sandboxes(self) -> SandboxesServiceApi:
        return SandboxesServiceApi(self._client.api_client)

    def run_command(
        self,
        sandbox_id: str,
        *,
        command: str,
        args: list[str] | None = None,
        organization_id: str | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        sudo: bool | None = None,
        detached: bool | None = None,
    ) -> dict[str, Any]:
        """Run a command in the sandbox via :meth:`SandboxesServiceApi.sandboxes_service_run_sandbox_command`.

        The JSON body is built from :meth:`_create_run_sandbox_command_body` so only fields defined on
        :class:`~lightning_sdk.lightning_cloud.openapi.models.SandboxesServiceRunSandboxCommandBody` are sent.
        Sandbox identity is carried by ``sandbox_id`` in the URL, not in the body.
        """
        body = self._create_run_sandbox_command_body(
            command=command,
            args=args,
            organization_id=organization_id,
            cwd=cwd,
            env=env,
            sudo=sudo,
            detached=detached,
        )
        api = self.sandboxes()
        try:
            resp = api.sandboxes_service_run_sandbox_command(body, sandbox_id)
        except ApiException as e:
            raise RuntimeError(f"Lightning API error {e.status}: {_api_exception_text(e)}") from e
        return _parse_run_command_response(resp)

    def get_command_logs(self, sandbox_id: str, cmd_id: str, organization_id: str | None = None) -> Any:
        """Fetch command logs via :meth:`SandboxesServiceApi.sandboxes_service_get_sandbox_command_logs`."""
        api = self.sandboxes()
        try:
            resp = api.sandboxes_service_get_sandbox_command_logs(
                sandbox_id,
                cmd_id,
                **({"organization_id": organization_id} if organization_id else {}),
            )
        except ApiException as e:
            raise RuntimeError(f"Lightning API error {e.status}: {_api_exception_text(e)}") from e
        return _parse_command_logs_response(resp)

    def kill_command(self, sandbox_id: str, cmd_id: str, organization_id: str | None) -> None:
        """Kill a running command via :meth:`SandboxesServiceApi.sandboxes_service_kill_sandbox_command`."""
        api = self.sandboxes()
        try:
            api.sandboxes_service_kill_sandbox_command(
                sandbox_id,
                cmd_id,
                **({"organization_id": organization_id} if organization_id else {}),
            )
        except ApiException as e:
            raise RuntimeError(f"Lightning API error {e.status}: {_api_exception_text(e)}") from e

    def get_command(self, sandbox_id: str, cmd_id: str, organization_id: str | None = None) -> dict[str, Any]:
        """Fetch command status via :meth:`SandboxesServiceApi.sandboxes_service_get_sandbox_command`."""
        api = self.sandboxes()
        try:
            resp = api.sandboxes_service_get_sandbox_command(
                sandbox_id,
                cmd_id,
                **({"organization_id": organization_id} if organization_id else {}),
            )
        except ApiException as e:
            raise RuntimeError(f"Lightning API error {e.status}: {_api_exception_text(e)}") from e
        return _parse_get_command_response(resp)

    def create_directory(self, sandbox_id: str, path: str, organization_id: str | None) -> None:
        """Create a directory via :meth:`SandboxesServiceApi.sandboxes_service_create_sandbox_directory`."""
        body = self._create_sandbox_directory_body(path=path, organization_id=organization_id)
        api = self.sandboxes()
        try:
            api.sandboxes_service_create_sandbox_directory(body, sandbox_id)
        except ApiException as e:
            raise RuntimeError(f"Lightning API error {e.status}: {_api_exception_text(e)}") from e
