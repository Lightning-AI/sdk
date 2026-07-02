from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lightning_sdk.lightning_cloud import env as lightning_env
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi import SandboxesServiceApi
from lightning_sdk.lightning_cloud.openapi.models import (
    SandboxesServiceCreateSandboxDirectoryBody,
    SandboxesServiceExtendSandboxTimeoutBody,
    SandboxesServiceRunSandboxCommandBody,
    V1ListSandboxesResponse,
    V1ListSandboxSnapshotsResponse,
    V1Sandbox,
    V1SandboxCommand,
    V1SandboxSnapshot,
)
from lightning_sdk.lightning_cloud.openapi.rest import ApiException
from lightning_sdk.lightning_cloud.rest_client import LightningClient


@dataclass
class CommandStatus:
    output: str
    exit_code: int
    #: ``True`` while the command is still executing; ``False`` once it has exited.
    #:
    #: Synchronous (non-``detached``) commands return ``False`` here once
    #: :meth:`~lightning_sdk.sandbox.base.SandboxInstance.run_command` returns. To
    #: check whether a ``detached`` command is still running, fetch its status via
    #: :meth:`~lightning_sdk.sandbox.base.SandboxInstance.get_command` (or block
    #: until completion with
    #: :meth:`~lightning_sdk.sandbox.base.SandboxInstance.wait_for_command`).
    running: bool = False


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


_PROJECT_SCOPED_KEY_HINT = (
    "This operation requires a teamspace-scoped API key. Create one in your Lightning "
    "teamspace (Members → API keys) and pass it via SandboxConfig(api_key=...) or "
    "LIGHTNING_SANDBOX_API_KEY. Org-scoped keys cannot snapshot or stop persistent "
    "sandboxes without a teamspace context."
)


_ORG_SCOPED_KEY_HINT = (
    "Use a teamspace- or org-scoped API key (Members → API keys), not your personal login key. "
    "Set LIGHTNING_SANDBOX_API_KEY or SandboxConfig(api_key=...)."
)


def _teamspace_key_project_mismatch_hint(teamspace: str | None = None) -> str:
    hint = (
        "Your teamspace-scoped API key is not authorized for the project requested via "
        "teamspace=. Each teamspace-scoped key is bound to one teamspace (project). "
        "Omit teamspace= to use the key's teamspace, or pass teamspace='owner/teamspace' "
        "that matches the key you created in Lightning (Members → API keys). "
        "To work in a different teamspace, switch to that teamspace's API key."
    )
    if teamspace:
        return f"{hint} You passed teamspace={teamspace!r}."
    return hint


def _is_org_id_required_error(exc: ApiException) -> bool:
    text = _api_exception_text(exc).lower().replace("_", " ")
    return "organization" in text and "id" in text and "required" in text


def _is_project_id_required_error(exc: ApiException) -> bool:
    text = _api_exception_text(exc).lower().replace("_", " ")
    return "project" in text and "id" in text and "required" in text


def _is_api_key_not_authorized_for_project_error(exc: ApiException) -> bool:
    if exc.status != 403:
        return False
    text = _api_exception_text(exc).lower()
    return "api key" in text and "not authorized" in text and "project" in text


def raise_sandbox_api_error(exc: ApiException, *, teamspace: str | None = None) -> None:
    """Map sandbox API failures to user-facing :class:`RuntimeError` messages."""
    if _is_api_key_not_authorized_for_project_error(exc):
        raise RuntimeError(_teamspace_key_project_mismatch_hint(teamspace)) from exc
    if _is_project_id_required_error(exc):
        raise RuntimeError(_PROJECT_SCOPED_KEY_HINT) from exc
    if _is_org_id_required_error(exc):
        raise RuntimeError(_ORG_SCOPED_KEY_HINT) from exc
    raise RuntimeError(f"Lightning API error {exc.status}: {_api_exception_text(exc)}") from exc


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
        return CommandStatus(output="", exit_code=0, running=False)
    d = resp.to_dict() if hasattr(resp, "to_dict") else {}
    return CommandStatus(
        output=str(d.get("output") or ""),
        exit_code=int(d.get("exit_code") or 0),
        running=bool(d.get("running") or False),
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
        self._client = LightningClient(max_tries=7, with_auth=False)
        self._auth_configured = False
        self._apply_auth_and_host()

    def config_get(self, key: str) -> Any:
        return self._config.get(key)

    def _org_query_kwargs(self, organization_id: str | None = None) -> dict[str, str]:
        if organization_id is not None:
            return {"organization_id": organization_id}
        return {}

    def reset(self) -> None:
        """Recreate the Lightning client and re-apply ``configure()`` / env (call after config changes)."""
        self._client = LightningClient(max_tries=7, with_auth=False)
        self._auth_configured = False
        self._apply_auth_and_host()

    invalidate = reset

    def _apply_auth_and_host(self) -> None:
        host = str(self._config.get("base_url") or lightning_env.LIGHTNING_CLOUD_URL).rstrip("/")
        self._client.api_client.configuration.host = host
        if self._config.get("api_key"):
            self._client.api_client.set_default_header("Authorization", f"Bearer {self._config['api_key']}")
            self._auth_configured = True
        else:
            self._auth_configured = False

    def _ensure_auth(self) -> None:
        if self._auth_configured:
            return
        auth_header = Auth().authenticate()
        if not auth_header:
            raise RuntimeError("Missing credentials: set api_key via configure() or use lightning login / env vars.")
        self._client.api_client.set_default_header("Authorization", auth_header)
        self._auth_configured = True

    @property
    def client(self) -> LightningClient:
        return self._client

    @property
    def host(self) -> str:
        return str(self._client.api_client.configuration.host).rstrip("/")

    def auth_header(self) -> str:
        """Return the configured Authorization header, authenticating lazily when needed."""
        self._ensure_auth()
        headers = getattr(self._client.api_client, "default_headers", {})
        auth = headers.get("Authorization", "") if isinstance(headers, dict) else ""
        return str(auth or "")

    def sandboxes(self) -> SandboxesServiceApi:
        self._ensure_auth()
        return SandboxesServiceApi(self._client.api_client)

    def get_sandbox(self, sandbox_id: str, *, organization_id: str | None = None) -> V1Sandbox:
        """Fetch one sandbox row via :meth:`SandboxesServiceApi.sandboxes_service_get_sandbox`."""
        api = self.sandboxes()
        try:
            v1 = api.sandboxes_service_get_sandbox(
                sandbox_id,
                **self._org_query_kwargs(organization_id),
            )
        except ApiException as e:
            raise_sandbox_api_error(e)
        return v1

    def extend_timeout(self, sandbox_id: str, *, timeout: int, organization_id: str | None = None) -> None:
        """Extend a sandbox's auto-stop deadline.

        Calls :meth:`SandboxesServiceApi.sandboxes_service_extend_sandbox_timeout`.

        ``timeout`` is the number of milliseconds to **add** to the sandbox's current
        deadline (the API requires at least 1000ms). Sandbox identity is carried by
        ``sandbox_id`` in the URL, not in the body.
        """
        body = SandboxesServiceExtendSandboxTimeoutBody(timeout=str(int(timeout)))
        if organization_id is not None:
            body.organization_id = organization_id
        api = self.sandboxes()
        try:
            api.sandboxes_service_extend_sandbox_timeout(body, sandbox_id)
        except ApiException as e:
            raise_sandbox_api_error(e)

    def list_sandboxes(
        self,
        *,
        page_token: str | None = None,
        limit: int | None = None,
        project_id: str | None = None,
    ) -> V1ListSandboxesResponse:
        """List sandboxes via :meth:`SandboxesServiceApi.sandboxes_service_list_sandboxes`."""
        kwargs = self._org_query_kwargs()
        if page_token:
            kwargs["page_token"] = page_token
        if limit is not None:
            kwargs["limit"] = limit
        if project_id:
            kwargs["project_id"] = project_id
        api = self.sandboxes()
        try:
            return api.sandboxes_service_list_sandboxes(**kwargs)
        except ApiException as e:
            raise_sandbox_api_error(e)

    def get_snapshot(self, snapshot_id: str, *, organization_id: str | None = None) -> V1SandboxSnapshot:
        """Fetch snapshot metadata via :meth:`SandboxesServiceApi.sandboxes_service_get_sandbox_snapshot`."""
        api = self.sandboxes()
        try:
            snap = api.sandboxes_service_get_sandbox_snapshot(
                snapshot_id,
                **self._org_query_kwargs(organization_id),
            )
        except ApiException as e:
            raise_sandbox_api_error(e)
        return snap

    def list_snapshots(
        self,
        *,
        name: str | None = None,
        page_token: str | None = None,
        limit: int | None = None,
        project_id: str | None = None,
        sort_order: str | None = None,
    ) -> V1ListSandboxSnapshotsResponse:
        """List snapshots via :meth:`SandboxesServiceApi.sandboxes_service_list_sandbox_snapshots`."""
        kwargs = self._org_query_kwargs()
        if name:
            kwargs["name"] = name
        if page_token:
            kwargs["page_token"] = page_token
        if limit is not None:
            kwargs["limit"] = str(limit)
        if project_id:
            kwargs["project_id"] = project_id
        if sort_order:
            kwargs["sort_order"] = sort_order
        api = self.sandboxes()
        try:
            return api.sandboxes_service_list_sandbox_snapshots(**kwargs)
        except ApiException as e:
            raise_sandbox_api_error(e)

    def delete_snapshot(self, snapshot_id: str, *, organization_id: str | None = None) -> None:
        """Delete a snapshot via :meth:`SandboxesServiceApi.sandboxes_service_delete_sandbox_snapshot`."""
        api = self.sandboxes()
        try:
            api.sandboxes_service_delete_sandbox_snapshot(
                snapshot_id,
                **self._org_query_kwargs(organization_id),
            )
        except ApiException as e:
            raise_sandbox_api_error(e)

    def run_command(
        self,
        sandbox_id: str,
        *,
        command: str,
        args: list[str] | None = None,
        organization_id: str | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
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
            detached=detached,
        )
        api = self.sandboxes()
        try:
            resp = api.sandboxes_service_run_sandbox_command(body, sandbox_id)
        except ApiException as e:
            raise_sandbox_api_error(e)
        return _parse_run_command_response(resp)

    def list_commands(self, sandbox_id: str, organization_id: str | None = None) -> list[V1SandboxCommand]:
        """List a sandbox's commands via :meth:`SandboxesServiceApi.sandboxes_service_list_sandbox_commands`.

        Returns the raw ``V1SandboxCommand`` rows (``id``, ``command``, ``exit_code``,
        ``output``, ``running``, ``created_at``, ``updated_at``); the sandbox layer
        wraps them in :class:`~lightning_sdk.sandbox.command.Command` via
        :meth:`Command._from_v1`.
        """
        api = self.sandboxes()
        try:
            resp = api.sandboxes_service_list_sandbox_commands(
                sandbox_id,
                **({"organization_id": organization_id} if organization_id else {}),
            )
        except ApiException as e:
            raise_sandbox_api_error(e)
        return list(resp.commands or [])

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
            raise_sandbox_api_error(e)
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
            raise_sandbox_api_error(e)

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
            raise_sandbox_api_error(e)
        return _parse_get_command_response(resp)

    def create_directory(self, sandbox_id: str, path: str, organization_id: str | None) -> None:
        """Create a directory via :meth:`SandboxesServiceApi.sandboxes_service_create_sandbox_directory`."""
        body = self._create_sandbox_directory_body(path=path, organization_id=organization_id)
        api = self.sandboxes()
        try:
            api.sandboxes_service_create_sandbox_directory(body, sandbox_id)
        except ApiException as e:
            raise_sandbox_api_error(e)
