# This file is vendored.
# Do not edit it directly; changes will be overwritten.
# Make changes in the internal upstream repository instead.

import base64
import contextlib
import dataclasses
import getpass
import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import sys
import tempfile
import time
import webbrowser
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

from lightning_sdk.lightning_cloud import env
from lightning_sdk.lightning_cloud.login import Auth

CLIENT_ID = "lightning-cli"
# Production serves this login only from relaunch, so until then a new login
# is the interim one unless this is set.
OIDC_LOGIN_ENV = "LIGHTNING_CLI_OIDC_LOGIN"
_KEYRING_SERVICE = CLIENT_ID
_REFRESH_MARGIN = 300.0
_PASTE_TRIES = 3
_CALLBACK_TIMEOUT = 300.0

_NOT_LOGGED_IN = "You are not logged in. Run `lightning login`."
_LOGIN_ENDED = "Your login has expired or was revoked. Run `lightning login`."
_REUSED = "refresh token was reused; the login is revoked"
_LOGIN_REUSED = (
    "This login was revoked because a copy of it was used elsewhere. "
    "Run `lightning login` and consider rotating any keys this machine held."
)
_BROWSER_TIMED_OUT = (
    "The browser didn't finish the login within 5 minutes, so nothing was saved. "
    "Run `lightning login` again, or `lightning login --no-browser` to paste a code instead."
)
_NO_KEYCHAIN = (
    "No OS keychain is available to store the login. Run "
    "`lightning login --no-keychain` to keep it in a file only you can read."
)
_PASTE_WARNING = (
    "The code gives access to your Lightning account. Paste it only into the "
    "CLI you just started, never into a website, form, chat or email."
)
_DEPLOYMENT = (
    "Failed to authenticate to Lightning. Ensure that you have selected "
    "'Include SDK credentials' in the 'Environment' section of the deployment settings."
)


class LoginError(ConnectionError):
    """A login could not be made, used or ended. The message says what to do next."""


class _Unreachable(LoginError):
    pass


class _Refused(LoginError):
    def __init__(self, error: str, description: str) -> None:
        super().__init__(f"Lightning refused the login: {description or error}.")
        self.error = error
        self.description = description


@dataclasses.dataclass(frozen=True)
class LoginStatus:
    url: str
    storage: str
    access_expires_at: float
    refresh_expires_at: float
    grant: Dict[str, Any]


@dataclasses.dataclass(frozen=True)
class Login(LoginStatus):
    access_token: str = dataclasses.field(repr=False)
    refresh_token: str = dataclasses.field(repr=False)


def oidc_login_enabled() -> bool:
    """Whether a new login uses this login rather than the interim one, read now."""
    return env.truthy(os.environ.get(OIDC_LOGIN_ENV))


def login(
    no_browser: bool = False,
    no_keychain: bool = False,
) -> Login:
    """Log in through the browser, or by pasting the code the login page shows."""
    if no_keychain:
        storage = _FileStorage.kind
    elif _keychain_available():
        storage = _KeychainStorage.kind
    else:
        raise LoginError(_NO_KEYCHAIN)
    attempt = _Attempt(_origin(), storage)
    if not no_browser:
        done = _browser_login(attempt)
        if done is not None:
            return done
        if os.environ.get("LIGHTNING_DEPLOYMENT_ID"):
            raise LoginError(_DEPLOYMENT)
    return _paste_back_login(attempt)


def token(min_remaining: float = 1800) -> str:
    """An access token with at least ``min_remaining`` seconds left, refreshed first if needed."""
    login = _fresh_login(_origin(), min_remaining)
    if login is None:
        raise LoginError(_NOT_LOGGED_IN)
    if login.access_expires_at - time.time() < min_remaining:
        raise LoginError(
            f"Couldn't refresh the login at {login.url}. Check your connection and try again."
        )
    return login.access_token


def current_login() -> Optional[LoginStatus]:
    """The saved login for this Lightning URL, without its tokens."""
    login = _load(_origin())
    if login is None:
        return None
    return LoginStatus(
        url=login.url,
        storage=login.storage,
        access_expires_at=login.access_expires_at,
        refresh_expires_at=login.refresh_expires_at,
        grant=login.grant,
    )


def _request_token(rejected: Optional[str] = None) -> Optional[str]:
    """The saved login's access token for a request, or None without a login.

    ``rejected`` is a token the server refused, which forces a refresh unless
    another process has already replaced it.
    """
    login = _fresh_login(_origin(), _REFRESH_MARGIN, rejected)
    return None if login is None else login.access_token


class _Attempt:
    """One login: its state, its PKCE verifier and where it will be stored."""

    def __init__(self, origin: str, storage: str) -> None:
        self.origin = origin
        self.storage = storage
        self.state = secrets.token_urlsafe(32)
        self._verifier = secrets.token_urlsafe(48)

    def authorize_url(self, redirect_uri: str) -> str:
        digest = hashlib.sha256(self._verifier.encode()).digest()
        query = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "openid",
            "state": self.state,
            "code_challenge": base64.urlsafe_b64encode(digest).rstrip(b"=").decode(),
            "code_challenge_method": "S256",
        }
        return f"{self.origin}/oidc/authorize?{urlencode(query)}"

    def complete(self, code: str, redirect_uri: str) -> Login:
        body = _token_endpoint({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._verifier,
            "storage": self.storage,
        })
        new = _login_from(body, self.storage, self.origin)

        def save() -> None:
            try:
                _save(new)
            except LoginError:
                _revoke(new.refresh_token)
                raise
            Auth.secrets_file.unlink(missing_ok=True)

        _replace_saved(save)
        return new


def _browser_login(attempt: _Attempt) -> Optional[Login]:
    redirect_uri = ""

    def complete(query: Dict[str, str]) -> Login:
        return _callback_login(attempt, query, redirect_uri)

    with _callback_server("/callback", complete, _BROWSER_TIMED_OUT) as (port, wait):
        redirect_uri = f"http://127.0.0.1:{port}/callback"
        url = attempt.authorize_url(redirect_uri)
        if not webbrowser.open(url):
            return None
        _say(
            f"Opening {url} in your browser to log in. "
            "If it doesn't open, run `lightning login --no-browser`."
        )
        return wait()


@contextlib.contextmanager
def _callback_server(
    path: str, complete: Callable[[Dict[str, str]], Any], timed_out: str
) -> Iterator[Tuple[int, Callable[[], Any]]]:
    """Serve one browser callback on 127.0.0.1, which ``complete`` turns into a login.

    ``wait()`` returns what ``complete`` returned, raises what it raised, or
    raises ``timed_out`` when no callback came within ``_CALLBACK_TIMEOUT``.
    """
    import http.server
    import socketserver

    origin = _origin()
    outcome = []

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            if parts.path != path:
                self.send_error(404)
                return
            query = {key: values[0] for key, values in parse_qs(parts.query).items()}
            try:
                outcome.append(complete(query))
                page = "cli-login-successful"
            except Exception as err:
                outcome.append(err)
                page = "cli-login-failed"
            self.send_response(302)
            self.send_header("Location", f"{origin}/{page}")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            # The default logs the request line, which carries the code or token.
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Callback) as server:
        # A short timeout lets Ctrl-C interrupt the wait.
        server.timeout = 0.5
        deadline = time.time() + _CALLBACK_TIMEOUT

        def wait() -> Any:
            while not outcome:
                if time.time() >= deadline:
                    raise LoginError(timed_out)
                server.handle_request()
            if isinstance(outcome[0], Exception):
                raise outcome[0]
            return outcome[0]

        yield server.server_address[1], wait


def _callback_login(attempt: _Attempt, query: Dict[str, str], redirect_uri: str) -> Login:
    if not hmac.compare_digest(query.get("state", "").encode(), attempt.state.encode()):
        raise LoginError(
            "The login callback didn't match this login, so nothing was saved. "
            "Run `lightning login` again."
        )
    if "error" in query:
        raise LoginError("The login was denied, so nothing was saved.")
    return attempt.complete(query.get("code", ""), redirect_uri)


def _paste_back_login(attempt: _Attempt) -> Login:
    redirect_uri = f"{attempt.origin}/cli-login"
    _say(
        "Open this URL on any device to log in:\n\n"
        f"    {attempt.authorize_url(redirect_uri)}\n\n{_PASTE_WARNING}\n"
    )
    for _ in range(_PASTE_TRIES):
        try:
            code = getpass.getpass("Paste the code from the login page: ").strip()
        except EOFError:
            raise LoginError("No code was entered. Run `lightning login` to try again.") from None
        if not code:
            _say("No code was entered.")
            continue
        try:
            return attempt.complete(code, redirect_uri)
        except _Refused as err:
            if err.error != "invalid_grant":
                raise
            _say("That code didn't work. It may have expired or been mistyped.")
    raise LoginError(
        f"No code worked after {_PASTE_TRIES} tries. Run `lightning login` to start again."
    )


def _fresh_login(url: str, min_remaining: float, rejected: Optional[str] = None) -> Optional[Login]:
    login = _load(url)
    if login is None or _usable(login, min_remaining, rejected):
        return login
    # Refresh tokens rotate, and presenting a retired one revokes the whole
    # login. So processes sharing it refresh one at a time, and each re-reads
    # the login under the lock in case another just refreshed it.
    with _locked():
        login = _load(url, cached=False)
        if login is None or _usable(login, min_remaining, rejected):
            return login
        try:
            body = _token_endpoint({
                "grant_type": "refresh_token",
                "refresh_token": login.refresh_token,
            })
        except _Unreachable:
            if rejected is None and login.access_expires_at > time.time():
                return login
            raise
        except _Refused as err:
            _forget()
            message = _LOGIN_REUSED if err.description == _REUSED else _LOGIN_ENDED
            raise LoginError(message) from None
        fresh = _login_from(body, login.storage, url)
        _save(fresh)
        return fresh


def _usable(login: Login, min_remaining: float, rejected: Optional[str]) -> bool:
    if rejected is not None:
        return login.access_token != rejected
    return login.access_expires_at - time.time() >= min_remaining


def _keychain_available() -> bool:
    try:
        import keyring

        return keyring.get_keyring().priority > 0
    except Exception:
        return False


class _KeychainStorage:
    """Tokens in the OS keychain, read only when the login file's version changes."""

    kind = "keychain"

    def __init__(self) -> None:
        self._cache = None

    def write(self, url: str, tokens: Dict[str, str]) -> Dict[str, str]:
        import keyring

        try:
            keyring.set_password(_KEYRING_SERVICE, url, json.dumps(tokens))
        except Exception as err:
            raise LoginError(_NO_KEYCHAIN) from err
        return {}

    def read(self, url: str, metadata: Dict[str, Any], cached: bool) -> Optional[Dict[str, str]]:
        key = (url, metadata.get("version"))
        if cached and self._cache is not None and self._cache[0] == key:
            return self._cache[1]
        import keyring

        try:
            tokens = _tokens(json.loads(keyring.get_password(_KEYRING_SERVICE, url) or "null"))
        except Exception:
            return None
        if tokens is not None and tokens["version"] == key[1]:
            self._cache = (key, tokens)
        return tokens

    def forget(self, url: str) -> None:
        self._cache = None
        import keyring

        with contextlib.suppress(Exception):
            keyring.delete_password(_KEYRING_SERVICE, url)


class _FileStorage:
    """Tokens in the login file itself, for --no-keychain."""

    kind = "file"

    def write(self, url: str, tokens: Dict[str, str]) -> Dict[str, str]:
        return tokens

    def read(self, url: str, metadata: Dict[str, Any], cached: bool) -> Optional[Dict[str, str]]:
        return _tokens(metadata)

    def forget(self, url: str) -> None:
        pass


_STORAGES = {storage.kind: storage for storage in (_KeychainStorage(), _FileStorage())}


def _tokens(data: Any) -> Optional[Dict[str, str]]:
    if not isinstance(data, dict):
        return None
    tokens = {key: data.get(key) for key in ("version", "access_token", "refresh_token")}
    if not all(isinstance(value, str) and value for value in tokens.values()):
        return None
    return tokens


def _load(url: str, cached: bool = True) -> Optional[Login]:
    metadata = _read_metadata()
    if metadata is None or metadata.get("url") != url:
        return None
    storage = _STORAGES.get(metadata.get("storage"))
    if storage is None:
        return None
    tokens = storage.read(url, metadata, cached)
    if tokens is None:
        return None
    try:
        access_expires_at = float(metadata["access_expires_at"])
        refresh_expires_at = float(metadata["refresh_expires_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if tokens["version"] != metadata.get("version"):
        # A save stopped between the keychain and the login file. The keychain
        # holds the newer pair, so refresh with it to rewrite both.
        access_expires_at = 0.0
    return Login(
        url=url,
        storage=storage.kind,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        grant=metadata.get("grant") or {},
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


def _save(login: Login) -> None:
    previous = _read_metadata()
    if previous and (previous.get("url"), previous.get("storage")) != (login.url, login.storage):
        _forget_secrets(previous)
    version = secrets.token_hex(16)
    tokens = {
        "version": version,
        "access_token": login.access_token,
        "refresh_token": login.refresh_token,
    }
    stored_here = _STORAGES[login.storage].write(login.url, tokens)
    _write_metadata({
        "version": version,
        "url": login.url,
        "storage": login.storage,
        "access_expires_at": login.access_expires_at,
        "refresh_expires_at": login.refresh_expires_at,
        "grant": login.grant,
        **stored_here,
    })


def _forget() -> None:
    metadata = _read_metadata()
    _retrying(_unlink, _login_path())
    if metadata is not None:
        _forget_secrets(metadata)


def _forget_secrets(metadata: Dict[str, Any]) -> None:
    storage = _STORAGES.get(metadata.get("storage"))
    if storage is not None and isinstance(metadata.get("url"), str):
        storage.forget(metadata["url"])


def _login_path() -> pathlib.Path:
    return pathlib.Path(env.LIGHTNING_LOGIN_PATH)


def _read_metadata() -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(_login_path().read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_metadata(data: Dict[str, Any]) -> None:
    path = _login_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file readable only by the user, and the rename keeps that.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(data, file)
        _retrying(os.replace, tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _unlink(path: pathlib.Path) -> None:
    path.unlink(missing_ok=True)


def _retrying(operation: Any, *args: Any) -> Any:
    for _ in range(50):
        try:
            return operation(*args)
        except PermissionError:
            # Windows refuses to replace or delete a file another process has open.
            time.sleep(0.02)
    return operation(*args)


@contextlib.contextmanager
def _locked() -> Iterator[None]:
    path = _login_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(f"{path}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock(fd)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


if os.name == "nt":
    import msvcrt

    def _lock(fd: int) -> None:
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.05)

    def _unlock(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _origin() -> str:
    return env.LIGHTNING_CLOUD_URL.rstrip("/")


def _post(path: str, form: Dict[str, str]) -> requests.Response:
    origin = _origin()
    try:
        return requests.post(
            f"{origin}{path}",
            data={"client_id": CLIENT_ID, **form},
            headers={"User-Agent": env.USER_AGENT},
            timeout=(env.LIGHTNING_CLOUD_CONNECT_TIMEOUT, env.LIGHTNING_CLOUD_READ_TIMEOUT),
            verify=env.SSL_CA_CERT,
        )
    except requests.RequestException as err:
        raise _Unreachable(f"Couldn't reach {origin}. Check your connection and try again.") from err


def _token_endpoint(form: Dict[str, str]) -> Dict[str, Any]:
    response = _post("/oidc/token", form)
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}
    if response.status_code == 200:
        return body
    error = str(body.get("error", ""))
    if response.status_code == 400 and error in ("invalid_grant", "access_denied"):
        raise _Refused(error, str(body.get("error_description", "")))
    if response.status_code >= 500 or response.status_code == 429:
        # The server is briefly unavailable or asking us to slow down. Unlike a
        # refusal, that says nothing about the token we hold, so a refresh that
        # hits it must not fail a request the token still covers.
        raise _Unreachable(
            f"Lightning answered the login request with {response.status_code}. Try again shortly."
        )
    raise LoginError(f"Lightning answered the login request with {response.status_code} {error}.")


def _revoke(token: str) -> bool:
    try:
        return _post("/oidc/revoke", {"token": token}).status_code == 200
    except _Unreachable:
        return False


def _revoke_session(token: str) -> bool:
    try:
        response = requests.post(
            f"{_origin()}/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}", "User-Agent": env.USER_AGENT},
            timeout=(env.LIGHTNING_CLOUD_CONNECT_TIMEOUT, env.LIGHTNING_CLOUD_READ_TIMEOUT),
            verify=env.SSL_CA_CERT,
        )
    except requests.RequestException:
        return False
    # A 401 says the session already doesn't work, which is all a revoke is for.
    return response.status_code in (200, 401)


def _saved_session() -> Optional[str]:
    """The interim ``sess_`` login saved as ``auth_token`` in credentials.json."""
    try:
        data = json.loads(Auth.secrets_file.read_text())
    except (OSError, ValueError):
        return None
    token = data.get("auth_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        return None
    return token.strip()


def _replace_saved(save: Callable[[], Optional[str]]) -> None:
    """Save a new login with ``save``, then revoke the logins it replaced.

    ``save`` returns the session token it saved, if it saved one. A ``save``
    that raises leaves the old logins saved and live.
    """
    with _locked():
        replaced_login = _load(_origin(), cached=False)
        replaced_session = _saved_session()
        kept_session = save()
    # credentials imports this module, so the shared wording is imported at the call.
    from lightning_sdk.lightning_cloud.credentials import REVOKE_FAILED, CredentialKind

    if replaced_login is not None and not _revoke(replaced_login.refresh_token):
        _say(REVOKE_FAILED[CredentialKind.LOGIN])
    if (
        replaced_session is not None
        and replaced_session != kept_session
        and not _revoke_session(replaced_session)
    ):
        _say(REVOKE_FAILED[CredentialKind.SESSION])


def _login_from(body: Dict[str, Any], storage: str, url: str) -> Login:
    try:
        return Login(
            url=url,
            storage=storage,
            access_expires_at=time.time() + float(body["expires_in"]),
            refresh_expires_at=_epoch(body["refresh_expires_at"]),
            grant=body.get("lightning_grant") or {},
            access_token=str(body["access_token"]),
            refresh_token=str(body["refresh_token"]),
        )
    except (KeyError, TypeError, ValueError):
        raise LoginError(
            "Lightning sent a login this SDK can't read. Upgrade the SDK and run `lightning login`."
        ) from None


# Python 3.9's datetime.fromisoformat reads neither "Z" nor nanoseconds, and Go writes both.
_RFC3339 = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?(Z|[+-]\d\d:\d\d)")


def _epoch(text: str) -> float:
    match = _RFC3339.fullmatch(text)
    if match is None:
        raise ValueError("not an RFC 3339 time")
    whole, fraction, zone = match.groups()
    zone = "+00:00" if zone == "Z" else zone
    return datetime.fromisoformat(whole + zone).timestamp() + float(fraction or 0)


def _say(message: str) -> None:
    print(message, file=sys.stderr)
