"""What the API lockdown lets through for the caller right now, as the control plane's ``/v1/config`` reports it.

The control plane sets the flags in grid-backend/pkg/storage/server/external_config.go. The capabilities are
the caller's own, so the request carries the caller's credentials. They only decide which notice the CLI shows:
the server enforces the lockdown, so while they can't be read the CLI lets the commands it can open run, and
turns the server's refusal into the same notice instead.
"""

import hashlib
import json
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Optional

import requests

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.lightning_cloud.openapi.rest import ApiException

LOCKDOWN_FLAG = "apiLockdown"
# Comma-separated names of the capabilities the caller holds. A capability missing from it is closed.
CAPABILITIES_FLAG = "apiLockdownCapabilities"

# The capabilities the CLI's gated commands need, named as grid-backend/pkg/apilockdown/capabilities.go names them.
RW_FILESYSTEM = "rw-filesystem"
STUDIOS = "studios"
STUDIO_DELETE = "studio-delete"
STUDIO_SIDECAR_AUTH = "studio-sidecar-auth"
STUDIO_SWITCHING = "studio-switching"
ENVIRONMENT_TEMPLATES = "environment-templates"
STUDIO_SSH = "studio-ssh"
USER_SECRETS = "user-secrets"
TEAMSPACE_SECRETS = "teamspace-secrets"
TEAMSPACE_SECRETS_WRITE = "teamspace-secrets-write"
JOBS = "jobs"
JOB_LIFECYCLE = "job-lifecycle"

_FETCH_TIMEOUT_SECONDS = 2
# short, so a capability the lockdown opens reaches the CLI within minutes
_CACHE_TTL_SECONDS = 5 * 60
_ORIGIN_REFUSAL = "this API is not available during maintenance"

_UNREAD = object()
_flags: Any = _UNREAD


def _cache_path() -> Path:
    return Path.home() / ".lightning" / "lockdown_flags.json"


def lockdown_flags() -> Optional[dict[str, bool]]:
    """The lockdown's flags for the caller from ``/v1/config``, or ``None`` when they can't be read.

    The result maps ``LOCKDOWN_FLAG`` to whether the lockdown is on, and each capability the caller holds to ``True``.
    They are fetched at most once per process, and read from a cache on disk for a few minutes after that. The
    cache is kept per account, so a different signed-in user never reads another user's capabilities.
    """
    global _flags
    if _flags is _UNREAD:
        auth_header = _auth_header()
        account = _account(auth_header)
        _flags = _read_cache(account)
        if _flags is None:
            _flags = _fetch(auth_header)
            if _flags is not None:
                _write_cache(_flags, account)
    return _flags


def lockdown_on() -> bool:
    """Whether the lockdown is on. Assumed on while the flags can't be read, as it was before they existed."""
    flags = lockdown_flags()
    return flags is None or flags.get(LOCKDOWN_FLAG, True)


def capability_closed(capability: str) -> bool:
    """Whether the lockdown is on and keeps the caller from the ``capability``.

    ``False`` while the flags can't be read: if the capability is closed, the server refuses the command.
    """
    flags = lockdown_flags()
    return flags is not None and flags.get(LOCKDOWN_FLAG, True) and not flags.get(capability, False)


def multi_machine_routes_closed() -> bool:
    """Whether the lockdown is on, so multi-machine job routes are refused.

    ``False`` while the flags can't be read. The request still goes out, and a refusal shows the usual notice.
    """
    flags = lockdown_flags()
    return flags is not None and flags.get(LOCKDOWN_FLAG, True)


def _auth_header() -> Optional[str]:
    """The credential requests would send, or ``None`` when there isn't one."""
    try:
        return Auth().auth_header
    except (ValueError, ConnectionError):
        return None


def _account(auth_header: Optional[str]) -> str:
    """A key for the caller's cache entries that doesn't reveal the credentials. Empty when signed out."""
    if auth_header is None:
        return ""
    return hashlib.sha256(auth_header.encode()).hexdigest()


def _parse_flags(flags: list[dict[str, Any]]) -> dict[str, bool]:
    """The control plane's feature flags as the lockdown reads them. Raises ``KeyError`` for a flag without a name."""
    parsed: dict[str, bool] = {}
    for flag in flags:
        name = flag["name"]
        if name == CAPABILITIES_FLAG:
            for capability in (flag.get("value") or "").split(","):
                if capability.strip():
                    parsed[capability.strip()] = True
        else:
            parsed[name] = flag.get("value") == "true"
    return parsed


def _fetch(auth_header: Optional[str]) -> Optional[dict[str, bool]]:
    headers = {"Authorization": auth_header} if auth_header else {}
    try:
        response = requests.get(f"{env.LIGHTNING_CLOUD_URL}/v1/config", headers=headers, timeout=_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
        return _parse_flags(response.json().get("featureFlags") or [])
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        # not cached, so the next command tries again
        return None


def _read_cache(account: str) -> Optional[dict[str, bool]]:
    """The cached flags for this cloud URL and account if they are fresh, else ``None``."""
    try:
        entry = json.loads(_cache_path().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or entry.get("url") != env.LIGHTNING_CLOUD_URL or entry.get("account") != account:
        return None
    checked_at = entry.get("checked_at")
    flags = entry.get("flags")
    if not isinstance(checked_at, (int, float)) or not isinstance(flags, dict):
        return None
    # a timestamp in the future would otherwise keep the entry alive indefinitely
    if not 0 <= time.time() - checked_at < _CACHE_TTL_SECONDS:
        return None
    return {name: value is True for name, value in flags.items()}


def _write_cache(flags: dict[str, bool], account: str) -> None:
    """Record the flags. Failing to write them only costs a repeated fetch next time."""
    path = _cache_path()
    entry = {"url": env.LIGHTNING_CLOUD_URL, "account": account, "flags": flags, "checked_at": time.time()}
    with suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        # write to a per-process file and rename, so concurrent commands never read a partial file
        tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
        tmp_path.write_text(json.dumps(entry))
        os.replace(tmp_path, path)


def is_lockdown_refusal(error: BaseException) -> bool:
    """Whether ``error``, or an error it was raised from, is the lockdown refusing a request.

    Cloudflare's block page is the only 403 served as HTML; the control plane answers with ``_ORIGIN_REFUSAL``.
    """
    seen: set[int] = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status, content_type, body = _response_of(current)
        if status == 403 and (content_type.startswith("text/html") or _ORIGIN_REFUSAL in body):
            return True
        current = current.__cause__ or current.__context__
    return False


def _response_of(error: BaseException) -> tuple[Optional[int], str, str]:
    """The status, content type and body of the HTTP response ``error`` carries, if any."""
    if isinstance(error, ApiException):
        status, headers, body = error.status, error.headers, error.body
    elif isinstance(error, requests.HTTPError) and error.response is not None:
        status, headers, body = error.response.status_code, error.response.headers, error.response.text
    else:
        return None, "", ""
    if isinstance(body, bytes):
        body = body.decode(errors="replace")
    content_type = (headers or {}).get("Content-Type") or ""
    return status, content_type, body or ""
