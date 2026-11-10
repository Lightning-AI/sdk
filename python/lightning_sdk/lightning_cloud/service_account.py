# This file is vendored.
# Do not edit it directly; changes will be overwritten.
# Make changes in the internal upstream repository instead.

"""The service-account key in ``LIGHTNING_API_KEY``, exchanged for short-lived access tokens.

The key is sent only to the token endpoint. Requests carry the access token it
is exchanged for, which this process reuses until it nears expiry.
"""

import dataclasses
import hashlib
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

import requests

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.cli_login import LoginError

KEY_ENV = "LIGHTNING_API_KEY"
_KEY_PREFIX = "lit_sa_"
# Exchange again with this long left, so no request leaves with a token that
# expires on the way.
_REFRESH_MARGIN = 300.0


class _Unavailable(LoginError):
    """The exchange didn't get an answer about the key, only about the server."""


@dataclasses.dataclass(frozen=True)
class _Token:
    # A digest of the origin and key, so a changed key or URL exchanges again.
    identity: str
    access_token: str = dataclasses.field(repr=False)
    expires_at: float


_lock = threading.Lock()
_current: Optional[_Token] = None


def _reset_after_fork() -> None:
    # A child forked while a thread was exchanging would inherit a held lock.
    global _lock
    _lock = threading.Lock()


os.register_at_fork(after_in_child=_reset_after_fork)


def key() -> Optional[str]:
    """The service-account key in ``LIGHTNING_API_KEY``, or None.

    Any other value, such as a user API key from before service accounts, is
    ignored and never sent.
    """
    value = (os.environ.get(KEY_ENV) or "").strip()
    return value if value.startswith(_KEY_PREFIX) else None


def token(rejected: Optional[str] = None) -> Optional[str]:
    """An access token for the service-account key in ``LIGHTNING_API_KEY``, or None without one.

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
            access_token, expires_in = _exchange(origin, presented)
        except _Unavailable:
            # An outage says nothing about the key, so a token with time left keeps working.
            if held is not None and rejected is None and held.expires_at > time.time():
                return held.access_token
            raise
        _current = _Token(identity, access_token, time.time() + expires_in)
        return access_token


def _usable(held: _Token, rejected: Optional[str]) -> bool:
    if rejected is not None:
        return held.access_token != rejected
    return held.expires_at - time.time() >= _REFRESH_MARGIN


def _origin() -> str:
    return env.LIGHTNING_CLOUD_URL.rstrip("/")


def _exchange(origin: str, presented: str) -> Tuple[str, float]:
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
            return access_token, float(expires_in)
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
