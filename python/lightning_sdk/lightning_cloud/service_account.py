"""The service-account key in ``LIGHTNING_API_KEY``, exchanged for short-lived access tokens.

The key is sent only to the token endpoint. Requests carry the access token it
is exchanged for, which this process reuses until it nears expiry.
"""

import dataclasses
import hashlib
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.cli_login import LoginError

KEY_ENV = "LIGHTNING_API_KEY"
# Exchange again with this long left, so no request leaves with a token that
# expires on the way.
_REFRESH_MARGIN = 300.0


class _Unavailable(LoginError):
    """The exchange didn't get an answer about the key, only about the server."""


@dataclasses.dataclass(frozen=True)
class KeyDetails:
    """What the exchange says about the key: the account it acts as, and when things expire.

    A server that predates these fields leaves them empty.
    """

    account_id: Optional[str]
    account_name: Optional[str]
    # An account always belongs to one org, whether or not it is a member of it.
    org_id: Optional[str]
    org_name: Optional[str]
    permissions: Tuple[str, ...]
    access_expires_at: float
    key_expires_at: Optional[float]


@dataclasses.dataclass(frozen=True)
class _Token:
    # A digest of the origin and key, so a changed key or URL exchanges again.
    identity: str
    access_token: str = dataclasses.field(repr=False)
    expires_at: float
    details: KeyDetails


_lock = threading.Lock()
_current: Optional[_Token] = None


def _reset_after_fork() -> None:
    # A child forked while a thread was exchanging would inherit a held lock.
    global _lock
    _lock = threading.Lock()


os.register_at_fork(after_in_child=_reset_after_fork)


def key() -> Optional[str]:
    """The key in ``LIGHTNING_API_KEY``, or None when it is unset or blank.

    Its shape isn't checked: a value that isn't a service-account key is
    refused by the exchange like any invalid credential.
    """
    value = (os.environ.get(KEY_ENV) or "").strip()
    return value or None


def token(rejected: Optional[str] = None) -> Optional[str]:
    """An access token for the key in ``LIGHTNING_API_KEY``, or None without one.

    ``rejected`` is a token the server refused, which forces a new exchange
    unless another thread has already replaced it.
    """
    global _current
    presented = key()
    if presented is None:
        return None
    origin = _origin()
    identity = hashlib.sha256(f"{origin}\0{presented}".encode()).hexdigest()
    with _lock:
        held = _current if _current is not None and _current.identity == identity else None
        if held is not None and _usable(held, rejected):
            return held.access_token
        try:
            access_token, expires_in, body = _exchange(origin, presented)
        except _Unavailable:
            # An outage says nothing about the key, so a token with time left keeps working.
            if held is not None and rejected is None and held.expires_at > time.time():
                return held.access_token
            raise
        expires_at = time.time() + expires_in
        _current = _Token(identity, access_token, expires_at, _details(body, expires_at))
        return access_token


def details() -> Optional[KeyDetails]:
    """What the exchange said about the key in ``LIGHTNING_API_KEY``, exchanging it if needed.

    None without a key.
    """
    if token() is None:
        return None
    with _lock:
        return _current.details if _current is not None else None


def _details(body: Dict[str, Any], access_expires_at: float) -> KeyDetails:
    account = body.get("service_account")
    account = account if isinstance(account, dict) else {}
    grant = body.get("lightning_grant")
    grant = grant if isinstance(grant, dict) else {}
    org_id = _text(account.get("org_id"))
    if org_id is None:
        # A key's grant names its account's one org.
        scopes = grant.get("orgs")
        if isinstance(scopes, list) and scopes and isinstance(scopes[0], dict):
            org_id = _text(scopes[0].get("org"))
    permissions = grant.get("permissions")
    return KeyDetails(
        account_id=_text(account.get("id")),
        account_name=_text(account.get("name")),
        org_id=org_id,
        org_name=_text(account.get("org_name")),
        permissions=tuple(p for p in permissions if isinstance(p, str)) if isinstance(permissions, list) else (),
        access_expires_at=access_expires_at,
        key_expires_at=_timestamp(body.get("key_expires_at")),
    )


def _text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _timestamp(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        # fromisoformat only accepts a trailing Z from Python 3.11.
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _usable(held: _Token, rejected: Optional[str]) -> bool:
    if rejected is not None:
        return held.access_token != rejected
    return held.expires_at - time.time() >= _REFRESH_MARGIN


def _origin() -> str:
    return env.LIGHTNING_CLOUD_URL.rstrip("/")


def _exchange(origin: str, presented: str) -> Tuple[str, float, Dict[str, Any]]:
    try:
        response = requests.post(
            f"{origin}/oidc/token",
            # No client_id: lightning-cli would route this to the browser login,
            # which refuses this grant. The key alone names its account.
            data={"grant_type": "client_credentials", "client_secret": presented},
            headers={"User-Agent": env.USER_AGENT},
            timeout=(env.LIGHTNING_CLOUD_CONNECT_TIMEOUT, env.LIGHTNING_CLOUD_READ_TIMEOUT),
            verify=env.SSL_CA_CERT,
        )
    except requests.RequestException as err:
        raise _Unavailable(
            f"Couldn't reach {origin} to exchange {KEY_ENV}. Check your connection and try again."
        ) from err
    body = _json(response)
    error = str(body.get("error", ""))
    status = response.status_code
    if status == 200:
        access_token = body.get("access_token")
        expires_in = body.get("expires_in")
        valid_expiry = isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool) and expires_in > 0
        if isinstance(access_token, str) and access_token and valid_expiry:
            return access_token, float(expires_in), body
        raise LoginError(f"Lightning answered the {KEY_ENV} exchange without a usable token.")
    if status == 401 and error == "invalid_client":
        reason = str(body.get("error_description", "")) or "invalid service account key"
        raise LoginError(
            f"Lightning refused the key in {KEY_ENV}: {reason}. "
            f"Use a current key, or unset {KEY_ENV} to use your login."
        )
    if status == 400 and error == "unsupported_grant_type":
        raise LoginError(f"{origin} doesn't accept service-account keys. Unset {KEY_ENV} to use your login.")
    if status >= 500 or status == 429:
        raise _Unavailable(f"Lightning answered the {KEY_ENV} exchange with {status}. Try again shortly.")
    raise LoginError(f"Lightning answered the {KEY_ENV} exchange with {status} {error}".rstrip() + ".")


def _json(response: requests.Response) -> Dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}
