"""What the API lockdown lets through right now, as the control plane's ``/v1/config`` reports it.

The control plane sets the flags in grid-backend/pkg/storage/server/external_config.go. They only decide
which notice the CLI shows: the server enforces the lockdown, so while they can't be read the CLI lets the
commands it can open run, and turns the server's refusal into the same notice instead.
"""

import json
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Optional

import requests

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.openapi.rest import ApiException

LOCKDOWN_FLAG = "apiLockdown"
UPLOADS_FLAG = "apiLockdownRWFilesystem"
STUDIOS_START_STOP_FLAG = "apiLockdownStudiosStartStop"
STUDIOS_SWITCHING_FLAG = "apiLockdownStudiosSwitching"
ENVIRONMENT_TEMPLATES_FLAG = "apiLockdownEnvironmentTemplates"
STUDIO_SSH_FLAG = "apiLockdownStudioSSH"

_FETCH_TIMEOUT_SECONDS = 2
# short, so a capability the lockdown opens reaches the CLI within minutes
_CACHE_TTL_SECONDS = 5 * 60
_ORIGIN_REFUSAL = "this API is not available during maintenance"

_UNREAD = object()
_flags: Any = _UNREAD


def _cache_path() -> Path:
    return Path.home() / ".lightning" / "lockdown_flags.json"


def lockdown_flags() -> Optional[dict[str, bool]]:
    """The lockdown's flags from ``/v1/config``, or ``None`` when they can't be read.

    They are fetched at most once per process, and read from a cache on disk for a few minutes after that.
    """
    global _flags
    if _flags is _UNREAD:
        _flags = _read_cache()
        if _flags is None:
            _flags = _fetch()
            if _flags is not None:
                _write_cache(_flags)
    return _flags


def lockdown_on() -> bool:
    """Whether the lockdown is on. Assumed on while the flags can't be read, as it was before they existed."""
    flags = lockdown_flags()
    return flags is None or flags.get(LOCKDOWN_FLAG, True)


def capability_closed(flag: str) -> bool:
    """Whether the lockdown is on and keeps closed the capability ``flag`` reports.

    ``False`` while the flags can't be read: if the capability is closed, the server refuses the command.
    """
    flags = lockdown_flags()
    return flags is not None and flags.get(LOCKDOWN_FLAG, True) and not flags.get(flag, False)


def _fetch() -> Optional[dict[str, bool]]:
    try:
        response = requests.get(f"{env.LIGHTNING_CLOUD_URL}/v1/config", timeout=_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
        return {flag["name"]: flag.get("value") == "true" for flag in response.json().get("featureFlags") or []}
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        # not cached, so the next command tries again
        return None


def _read_cache() -> Optional[dict[str, bool]]:
    """The cached flags for this cloud URL if they are fresh, else ``None``."""
    try:
        entry = json.loads(_cache_path().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or entry.get("url") != env.LIGHTNING_CLOUD_URL:
        return None
    checked_at = entry.get("checked_at")
    flags = entry.get("flags")
    if not isinstance(checked_at, (int, float)) or not isinstance(flags, dict):
        return None
    # a timestamp in the future would otherwise keep the entry alive indefinitely
    if not 0 <= time.time() - checked_at < _CACHE_TTL_SECONDS:
        return None
    return {name: value is True for name, value in flags.items()}


def _write_cache(flags: dict[str, bool]) -> None:
    """Record the flags. Failing to write them only costs a repeated fetch next time."""
    path = _cache_path()
    entry = {"url": env.LIGHTNING_CLOUD_URL, "flags": flags, "checked_at": time.time()}
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
